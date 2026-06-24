"""
Batch loader for cached literature results.

Reads literature data from literature_cache.db (raw sqlite3) and
returns a list of LiteratureDocument objects for downstream extraction.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from app.literature.cache import LiteratureCache

logger = logging.getLogger(__name__)


@dataclass
class LiteratureDocument:
    """Unified document representation for extraction pipeline."""
    literature_id: int
    title: str = ""
    abstract: Optional[str] = None
    fulltext: Optional[str] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    pmid: Optional[str] = None
    source_databases: list[str] = field(default_factory=list)
    ranking_score: Optional[float] = None
    pdf_url: Optional[str] = None
    fulltext_available: bool = False
    citation_count: Optional[int] = None
    publication_type: Optional[str] = None
    journal: Optional[str] = None
    raw: Optional[dict] = None

    def get_text(self, include_fulltext: bool = True) -> str:
        """Get combined text for extraction, ordered by priority."""
        parts = []
        if self.title:
            parts.append(self.title)
        if self.abstract:
            parts.append(self.abstract)
        if include_fulltext and self.fulltext:
            parts.append(self.fulltext)
        return "\n\n".join(parts)

    def has_content(self) -> bool:
        """Check if document has any searchable content."""
        return bool(self.title or self.abstract or self.fulltext)


def load_literature_batch(
    query_id: Optional[int] = None,
    literature_ids: Optional[list[int]] = None,
    limit: Optional[int] = None,
    include_fulltext: bool = True,
    cache: Optional[LiteratureCache] = None,
) -> list[LiteratureDocument]:
    """Load literature results from the cache database.

    Args:
        query_id: Load all results for a specific query.
        literature_ids: Load specific results by ID.
        limit: Maximum number of documents to return.
        include_fulltext: Whether to attempt loading fulltext content.
        cache: Optional LiteratureCache instance (creates one if not provided).

    Returns:
        List of LiteratureDocument objects ready for extraction.
    """
    if cache is None:
        cache = LiteratureCache()

    docs: list[LiteratureDocument] = []
    skipped = 0

    if literature_ids:
        for lid in literature_ids:
            row = cache.conn.execute(
                "SELECT * FROM literature_results WHERE id = ?", (lid,)
            ).fetchone()
            if row:
                doc = _row_to_document(dict(row))
                if doc.has_content():
                    docs.append(doc)
                else:
                    skipped += 1
                    logger.warning(f"Literature {lid}: no title/abstract/fulltext, skipped")
    elif query_id:
        rows = cache.conn.execute(
            "SELECT * FROM literature_results WHERE query_id = ? ORDER BY final_score DESC",
            (query_id,),
        ).fetchall()
        for row in rows:
            d = dict(row)
            doc = _row_to_document(d)
            if doc.has_content():
                docs.append(doc)
            else:
                skipped += 1
        if limit:
            docs = docs[:limit]
    else:
        rows = cache.conn.execute(
            "SELECT * FROM literature_results ORDER BY final_score DESC LIMIT ?",
            (limit or 100,),
        ).fetchall()
        for row in rows:
            d = dict(row)
            doc = _row_to_document(d)
            if doc.has_content():
                docs.append(doc)
            else:
                skipped += 1

    logger.info(
        f"Loaded {len(docs)} documents (query_id={query_id}, "
        f"literature_ids={literature_ids}, skipped={skipped})"
    )
    return docs


def _row_to_document(row: dict) -> LiteratureDocument:
    """Convert a cache DB row to a LiteratureDocument."""
    import json as _json

    source_dbs = []
    try:
        source_dbs = _json.loads(row.get("source_databases_json", "[]") or "[]")
    except (_json.JSONDecodeError, TypeError):
        pass

    raw = {}
    try:
        raw = _json.loads(row.get("raw_json", "{}") or "{}")
    except (_json.JSONDecodeError, TypeError):
        pass

    return LiteratureDocument(
        literature_id=row.get("id") or 0,
        title=row.get("title") or "",
        abstract=row.get("abstract"),
        fulltext=row.get("fulltext_url"),
        year=row.get("year"),
        doi=row.get("doi"),
        pmid=row.get("pmid"),
        source_databases=source_dbs,
        ranking_score=row.get("final_score"),
        pdf_url=row.get("pdf_url"),
        fulltext_available=bool(row.get("fulltext_available")),
        citation_count=row.get("citation_count"),
        publication_type=row.get("publication_type"),
        journal=row.get("journal"),
        raw=raw,
    )


def get_cached_queries(cache: Optional[LiteratureCache] = None) -> list[dict]:
    """Get all cached search queries."""
    if cache is None:
        cache = LiteratureCache()
    rows = cache.conn.execute(
        "SELECT * FROM literature_queries ORDER BY created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]
