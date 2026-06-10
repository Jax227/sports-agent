"""Vector store — semantic search using embeddings."""

import os
from pathlib import Path
from typing import Optional

from src.config import CHROMA_PERSIST_DIR, EMBEDDING_MODEL, LOCAL_EMBEDDING_MODEL
from src.utils import logger

# Lazy-loaded singletons
_chroma_client = None
_embedding_fn = None
_collection = None


def _get_embedding_fn():
    """Get embedding function — tries OpenAI first, then local SentenceTransformer."""
    global _embedding_fn

    if _embedding_fn is not None:
        return _embedding_fn

    # Try OpenAI embeddings
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        try:
            from chromadb.utils import embedding_functions
            _embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
                api_key=openai_key,
                model_name="text-embedding-3-small",
            )
            logger.info("Using OpenAI embeddings (text-embedding-3-small)")
            return _embedding_fn
        except Exception as e:
            logger.warning(f"Failed to init OpenAI embeddings: {e}")

    # Fall back to local SentenceTransformer
    try:
        from chromadb.utils import embedding_functions
        model_name = LOCAL_EMBEDDING_MODEL or "all-MiniLM-L6-v2"
        _embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=model_name,
        )
        logger.info(f"Using local SentenceTransformer embeddings: {model_name}")
        return _embedding_fn
    except Exception as e:
        logger.error(f"Failed to init SentenceTransformer embeddings: {e}")
        return None


def _get_client():
    """Get or create ChromaDB client."""
    global _chroma_client
    if _chroma_client is not None:
        return _chroma_client

    try:
        import chromadb
        CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))
        logger.info(f"ChromaDB client initialized at {CHROMA_PERSIST_DIR}")
        return _chroma_client
    except ImportError:
        logger.error("chromadb not installed. Install with: pip install chromadb")
        return None
    except Exception as e:
        logger.error(f"Failed to init ChromaDB: {e}")
        return None


def get_collection(name: str = "sports_science_papers"):
    """Get or create a ChromaDB collection."""
    global _collection
    client = _get_client()
    if client is None:
        return None

    embedding_fn = _get_embedding_fn()
    if embedding_fn is None:
        return None

    try:
        _collection = client.get_or_create_collection(
            name=name,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        return _collection
    except Exception as e:
        logger.error(f"Failed to get/create collection: {e}")
        return None


def add_paper_to_vector_store(paper: dict) -> bool:
    """Add a paper to the vector store."""
    collection = get_collection()
    if collection is None:
        return False

    paper_id = paper.get("id", "")
    if not paper_id:
        return False

    # Build document text for embedding
    doc_parts = [
        f"Title: {paper.get('title', '')}",
        f"Abstract: {paper.get('abstract', '')}",
        f"Keywords: {paper.get('keywords', '')}",
        f"Main Findings: {paper.get('main_findings', '')}",
    ]
    doc_text = "\n".join(doc_parts)[:8000]  # Truncate for embedding

    metadata = {
        "title": str(paper.get("title", ""))[:500],
        "authors": str(paper.get("authors", ""))[:300],
        "year": str(paper.get("year", "")),
        "journal": str(paper.get("journal", ""))[:300],
        "study_type": str(paper.get("study_type", "")),
        "evidence_level": str(paper.get("evidence_level", "")),
        "research_domain": str(paper.get("research_domain", "")),
        "quality_score": str(paper.get("quality_score", "")),
        "relevance_score": str(paper.get("relevance_score", "")),
        "doi": str(paper.get("doi", "")),
        "pmid": str(paper.get("pmid", "")),
    }

    try:
        # Use upsert to avoid duplicates
        collection.upsert(
            ids=[paper_id],
            documents=[doc_text],
            metadatas=[metadata],
        )
        logger.info(f"Added to vector store: {paper.get('title', '')[:80]}")
        return True
    except Exception as e:
        logger.error(f"Failed to add to vector store: {e}")
        return False


def semantic_search(query: str, n_results: int = 10, filters: Optional[dict] = None) -> list[dict]:
    """Semantic search over the literature vector store."""
    collection = get_collection()
    if collection is None:
        return []

    where_filter = None
    if filters:
        where_filter = {}
        for k, v in filters.items():
            if v:
                where_filter[k] = v

    try:
        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, collection.count()),
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
        if not results or not results.get("ids") or not results["ids"][0]:
            return []

        papers = []
        for i, paper_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            distance = results["distances"][0][i] if results.get("distances") else 1.0
            doc = results["documents"][0][i] if results.get("documents") else ""

            papers.append({
                "id": paper_id,
                **meta,
                "cosine_distance": round(distance, 4),
                "snippet": doc[:500] if doc else "",
            })

        return papers
    except Exception as e:
        logger.error(f"Semantic search error: {e}")
        return []


def rebuild_index(papers: list[dict]):
    """Rebuild the vector store from a list of papers."""
    # Delete existing collection and recreate
    client = _get_client()
    if client:
        try:
            client.delete_collection("sports_science_papers")
        except Exception:
            pass

    collection = get_collection("sports_science_papers")
    if collection is None:
        return

    batch_size = 50
    for i in range(0, len(papers), batch_size):
        batch = papers[i:i + batch_size]
        ids = []
        docs = []
        metas = []
        for paper in batch:
            pid = paper.get("id", "")
            if not pid:
                continue
            ids.append(pid)
            doc_parts = [
                f"Title: {paper.get('title', '')}",
                f"Abstract: {paper.get('abstract', '')}",
                f"Keywords: {paper.get('keywords', '')}",
                f"Main Findings: {paper.get('main_findings', '')}",
            ]
            docs.append("\n".join(doc_parts)[:8000])
            metas.append({
                "title": str(paper.get("title", ""))[:500],
                "authors": str(paper.get("authors", ""))[:300],
                "year": str(paper.get("year", "")),
                "journal": str(paper.get("journal", ""))[:300],
                "study_type": str(paper.get("study_type", "")),
                "evidence_level": str(paper.get("evidence_level", "")),
                "research_domain": str(paper.get("research_domain", "")),
                "quality_score": str(paper.get("quality_score", "")),
            })
        if ids:
            collection.add(ids=ids, documents=docs, metadatas=metas)

    logger.info(f"Vector store rebuilt with {collection.count()} documents")


def get_vector_store_stats() -> dict:
    """Get statistics about the vector store."""
    collection = get_collection()
    if collection is None:
        return {"status": "unavailable", "count": 0}
    return {
        "status": "available",
        "count": collection.count(),
        "name": collection.name,
        "embedding_model": LOCAL_EMBEDDING_MODEL or EMBEDDING_MODEL,
    }
