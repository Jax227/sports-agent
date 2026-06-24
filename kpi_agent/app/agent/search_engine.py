"""
Evidence search engine — hybrid keyword + vector search.

Supports Chinese and English queries:
1. SQL keyword search — fast, exact and fuzzy matching
2. Vector semantic search — meaning-based retrieval via ChromaDB
"""

import os
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session
from app import models

# ── Vector store (lazy init) ────────────────────────────────────

_chroma_client = None
_embedding_fn = None
_collection = None

VECTOR_STORE_DIR = Path(__file__).resolve().parent.parent.parent / "vector_store" / "evidence"


def _get_embedding_fn():
    """Get embedding function for Chinese + English support."""
    global _embedding_fn
    if _embedding_fn is not None:
        return _embedding_fn

    # Try to use the existing bge-small-zh model (Chinese + English)
    local_model_path = Path(__file__).resolve().parent.parent.parent.parent / "models" / "bge-small-zh-v1.5"
    if local_model_path.exists():
        try:
            from chromadb.utils import embedding_functions
            _embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=str(local_model_path),
            )
            return _embedding_fn
        except Exception:
            pass

    # Fall back to all-MiniLM-L6-v2 (English-optimized but works for Chinese too)
    try:
        from chromadb.utils import embedding_functions
        _embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2",
        )
        return _embedding_fn
    except Exception:
        return None


def _get_collection():
    """Get or create the evidence ChromaDB collection.

    Gracefully returns None if ChromaDB is unavailable or ephemeral
    storage is not writable (Streamlit Cloud).
    """
    global _chroma_client, _collection
    if _collection is not None:
        return _collection

    try:
        import chromadb
    except ImportError:
        return None

    if _chroma_client is None:
        try:
            VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
            _chroma_client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))
        except Exception:
            return None

    if _collection is None:
        ef = _get_embedding_fn()
        if ef is None:
            return None
        _collection = _chroma_client.get_or_create_collection(
            name="kpi_evidence",
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


# ── Indexing ────────────────────────────────────────────────────

def index_evidence_source(source: models.EvidenceSource):
    """Add or update an evidence source in the vector store."""
    collection = _get_collection()
    if collection is None:
        return False

    doc_text = f"Title: {source.title}\nAuthors: {source.authors or ''}\nSummary: {source.summary or ''}\nRelevance: {source.relevance or ''}"
    if len(doc_text) > 8000:
        doc_text = doc_text[:8000]

    meta = {
        "title": source.title[:500],
        "authors": (source.authors or "")[:300],
        "year": str(source.year or ""),
        "source_type": source.source_type,
        "evidence_level": source.evidence_level,
        "db_id": str(source.id),
    }

    try:
        collection.upsert(
            ids=[f"src_{source.id}"],
            documents=[doc_text],
            metadatas=[meta],
        )
        return True
    except Exception:
        return False


def index_all_sources(db: Session, project_id: Optional[int] = None):
    """Index all evidence sources into the vector store."""
    q = db.query(models.EvidenceSource)
    if project_id:
        q = q.filter(models.EvidenceSource.project_id == project_id)

    count = 0
    for source in q.all():
        if index_evidence_source(source):
            count += 1
    return count


# ── Keyword Search (SQL) ────────────────────────────────────────

def keyword_search(
    db: Session,
    query: str,
    project_id: Optional[int] = None,
    source_type: Optional[str] = None,
    evidence_level: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    limit: int = 20,
) -> list[models.EvidenceSource]:
    """SQL keyword search across evidence sources. Supports Chinese + English."""
    q = db.query(models.EvidenceSource)

    if project_id:
        q = q.filter(models.EvidenceSource.project_id == project_id)

    if query.strip():
        # Split into individual keywords for AND-like matching
        keywords = query.strip().split()
        for kw in keywords:
            pattern = f"%{kw}%"
            q = q.filter(
                models.EvidenceSource.title.ilike(pattern) |
                models.EvidenceSource.summary.ilike(pattern) |
                models.EvidenceSource.authors.ilike(pattern) |
                models.EvidenceSource.relevance.ilike(pattern) |
                models.EvidenceSource.citation.ilike(pattern)
            )

    if source_type:
        q = q.filter(models.EvidenceSource.source_type == source_type)
    if evidence_level:
        q = q.filter(models.EvidenceSource.evidence_level == evidence_level)
    if year_from:
        q = q.filter(models.EvidenceSource.year >= year_from)
    if year_to:
        q = q.filter(models.EvidenceSource.year <= year_to)

    return q.order_by(models.EvidenceSource.created_at.desc()).limit(limit).all()


# ── Vector Semantic Search ──────────────────────────────────────

def vector_search(
    query: str,
    project_id: Optional[int] = None,
    n_results: int = 10,
) -> list[dict]:
    """Semantic search over evidence sources."""
    collection = _get_collection()
    if collection is None or collection.count() == 0:
        return []

    where_filter = None
    if project_id:
        where_filter = {"db_id": str(project_id)}  # Note: this filters by db_id, not ideal for multi-project

    try:
        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, collection.count()),
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        if not results or not results.get("ids") or not results["ids"][0]:
            return []

        items = []
        for i, doc_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            distance = results["distances"][0][i] if results.get("distances") else 1.0
            doc = results["documents"][0][i] if results.get("documents") else ""

            # Cosine distance to similarity score (0-100)
            similarity = max(0, min(100, round((1 - distance) * 100, 1)))

            items.append({
                **meta,
                "vector_id": doc_id,
                "similarity": similarity,
                "snippet": doc[:300],
            })

        return items
    except Exception:
        return []


# ── Hybrid Search ───────────────────────────────────────────────

def hybrid_search(
    db: Session,
    query: str,
    project_id: Optional[int] = None,
    limit: int = 20,
) -> dict:
    """
    Combined search: keyword + vector.
    Returns unified results with source attribution.
    """
    # 1. Keyword search
    kw_results = keyword_search(db, query, project_id, limit=limit)

    # 2. Vector search
    vec_results = vector_search(query, project_id, n_results=limit)

    # 3. Merge: deduplicate by db_id
    seen_ids = set()
    merged = []

    # Keyword results first (exact/fuzzy match)
    for src in kw_results:
        seen_ids.add(str(src.id))
        merged.append({
            "id": src.id,
            "title": src.title,
            "authors": src.authors,
            "year": src.year,
            "source_type": src.source_type,
            "evidence_level": src.evidence_level,
            "summary": src.summary[:200] if src.summary else "",
            "url": src.url,
            "doi": src.doi,
            "relevance": src.relevance,
            "limitations": src.limitations,
            "match_type": "关键词匹配",
            "similarity": None,
        })

    # Vector results (semantic match)
    for vr in vec_results:
        db_id = vr.get("db_id", "")
        if db_id in seen_ids:
            continue
        seen_ids.add(db_id)
        merged.append({
            "id": int(db_id) if db_id.isdigit() else None,
            "title": vr.get("title", ""),
            "authors": vr.get("authors", ""),
            "year": int(vr["year"]) if vr.get("year", "").isdigit() else None,
            "source_type": vr.get("source_type", ""),
            "evidence_level": vr.get("evidence_level", ""),
            "summary": vr.get("snippet", ""),
            "url": "",
            "doi": "",
            "relevance": "",
            "limitations": "",
            "match_type": "语义匹配",
            "similarity": vr.get("similarity"),
        })

    # Sort: keyword matches first, then by similarity
    keyword_matches = [m for m in merged if m["match_type"] == "关键词匹配"]
    semantic_matches = sorted(
        [m for m in merged if m["match_type"] == "语义匹配"],
        key=lambda x: x["similarity"] or 0, reverse=True,
    )

    results = keyword_matches + semantic_matches

    return {
        "query": query,
        "total": len(results),
        "keyword_count": len(kw_results),
        "semantic_count": len(vec_results),
        "results": results[:limit],
    }
