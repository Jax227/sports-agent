"""
Literature search & extraction API endpoints.

Endpoints:
- POST /literature/search-free — multi-source search
- POST /literature/enrich-fulltext — fulltext link discovery
- POST /literature/rerank — re-rank results
- POST /extraction/free-extract — rule-based evidence extraction
- GET /evidence/matrix — evidence matrix generation
- GET /connectors/status — connector health check
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.literature.connectors.registry import ConnectorRegistry, search_all_sources
from app.literature.dedup import deduplicate_results
from app.literature.cache import LiteratureCache
from app.literature.fulltext import enrich_fulltext_links
from app.literature.ranking import hybrid_rerank
from app.literature.extraction import batch_extract
from app.literature.matrix import generate_evidence_matrix
from app.literature.schema import LiteratureResult, EvidenceMatrix

router = APIRouter(prefix="/literature", tags=["literature"])


# ── Request schemas ────────────────────────────────────────────────

class SearchFreeRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Search query")
    sources: list[str] = Field(
        default=["openalex", "pubmed", "europe_pmc", "crossref", "semantic_scholar"],
        description="Data sources to query",
    )
    limit_per_source: int = Field(default=20, ge=1, le=50, description="Max results per source")
    refresh: bool = Field(default=False, description="Force re-fetch, skip cache")
    enrich_fulltext: bool = Field(default=True, description="Discover OA fulltext links")
    rerank: bool = Field(default=True, description="Hybrid re-ranking")
    sport_context: Optional[str] = Field(default=None, description="Sport context for ranking boost")


class EnrichFulltextRequest(BaseModel):
    literature_ids: list[int] = Field(..., description="Literature IDs to enrich")


class RerankRequest(BaseModel):
    query: str = Field(..., min_length=2)
    literature_ids: list[int] = Field(..., description="Literature IDs to re-rank")
    sport_context: Optional[str] = None


class FreeExtractRequest(BaseModel):
    literature_ids: list[int] = Field(..., description="Literature IDs to extract from")


# ── Endpoints ──────────────────────────────────────────────────────

@router.post("/search-free")
def search_free(req: SearchFreeRequest):
    """Multi-source free literature search with dedup, cache, fulltext, and rerank."""
    cache = LiteratureCache()
    cache_key = LiteratureCache.make_cache_key(req.query, req.sources)

    # Check cache
    cached_query = None
    if not req.refresh:
        cached_query = cache.get_cached_query(cache_key)

    if cached_query:
        cached_results = cache.get_cached_results(cached_query["id"])
        results = [LiteratureResult.from_dict(r) for r in cached_results]

        return {
            "query": req.query,
            "cached": True,
            "source_counts": {},
            "deduplication_report": {"before_count": len(results), "after_count": len(results), "duplicates_removed": 0},
            "results": [r.to_dict() for r in results],
            "total": len(results),
        }

    # 1. Search all sources
    search_result = search_all_sources(
        query=req.query,
        sources=req.sources,
        limit_per_source=req.limit_per_source,
    )

    raw_results = search_result["results"]

    # 2. Deduplicate
    dedup_report = deduplicate_results(raw_results)
    results = dedup_report["results"]

    # 3. Fulltext enrichment
    if req.enrich_fulltext:
        results = enrich_fulltext_links(results, use_unpaywall=True)

    # 4. Hybrid re-rank
    if req.rerank:
        results = hybrid_rerank(req.query, results, sport_context=req.sport_context)

    # 5. Cache
    query_id = cache.save_query(
        req.query, req.sources, None, cache_key,
        result_count=len(results),
    )
    cache.save_results(query_id, results)

    # Log per-source
    for src_name, count in search_result.get("source_counts", {}).items():
        cache.log_retrieval(query_id, src_name, result_count=count)

    return {
        "query": req.query,
        "cached": False,
        "source_counts": search_result.get("source_counts", {}),
        "source_status": search_result.get("source_status", []),
        "errors": search_result.get("errors", []),
        "deduplication_report": {
            "before_count": dedup_report["before_count"],
            "after_count": dedup_report["after_count"],
            "duplicates_removed": dedup_report["duplicates_removed"],
            "merge_details": dedup_report.get("merge_details", []),
        },
        "results": [r.to_dict() for r in results],
        "total": len(results),
    }


@router.post("/enrich-fulltext-links")
def enrich_fulltext(req: EnrichFulltextRequest):
    """Discover OA fulltext links for specific literature IDs from cache."""
    cache = LiteratureCache()
    results = []
    for lid in req.literature_ids:
        cached = cache.get_cached_results(0)  # query_id=0 won't match, need direct lookup
        # For now, we can't easily get individual results from cache by id
        # This is a placeholder for future enhancement
        pass

    return {"updated": 0, "links": [], "message": "Use search-free with enrich_fulltext=true for fulltext discovery"}


@router.post("/rerank")
def rerank(req: RerankRequest):
    """Re-rank literature results by hybrid scoring."""
    if not req.literature_ids:
        return {"results": []}

    cache = LiteratureCache()
    # Get cached results — this requires them to have been cached with a query
    conn = cache.conn
    placeholders = ",".join("?" for _ in req.literature_ids)
    rows = conn.execute(
        f"SELECT * FROM literature_results WHERE id IN ({placeholders})",
        req.literature_ids,
    ).fetchall()

    results = [LiteratureResult.from_dict(dict(r)) for r in rows]

    if results:
        results = hybrid_rerank(req.query, results, sport_context=req.sport_context)

    return {
        "results": [r.to_dict() for r in results],
        "total": len(results),
    }


@router.post("/extraction/free-extract")
def free_extract(req: FreeExtractRequest):
    """Rule-based evidence extraction from literature results."""
    cache = LiteratureCache()
    conn = cache.conn

    if not req.literature_ids:
        return {"extractions": [], "total": 0}

    placeholders = ",".join("?" for _ in req.literature_ids)
    rows = conn.execute(
        f"SELECT * FROM literature_results WHERE id IN ({placeholders})",
        req.literature_ids,
    ).fetchall()

    results = [LiteratureResult.from_dict(dict(r)) for r in rows]
    extractions = batch_extract(results)

    return {
        "extractions": [e.to_dict() for e in extractions],
        "total": len(extractions),
    }


@router.get("/evidence/matrix")
def evidence_matrix(
    query: Optional[str] = None,
    format: str = "json",
):
    """Generate evidence matrix from the most recent search results in cache."""
    cache = LiteratureCache()
    conn = cache.conn

    # Get most recent query
    query_row = conn.execute(
        "SELECT * FROM literature_queries ORDER BY created_at DESC LIMIT 1"
    ).fetchone()

    if not query_row:
        raise HTTPException(status_code=404, detail="No cached search results found")

    query_text = query or dict(query_row)["query_text"]
    query_id = dict(query_row)["id"]

    rows = conn.execute(
        "SELECT * FROM literature_results WHERE query_id = ? ORDER BY final_score DESC",
        (query_id,),
    ).fetchall()

    results = [LiteratureResult.from_dict(dict(r)) for r in rows]

    # Extract
    extractions = batch_extract(results)

    # Generate matrix
    matrix = generate_evidence_matrix(query_text, results, extractions)

    if format == "markdown":
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(matrix.to_markdown(), media_type="text/markdown")
    elif format == "csv":
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(matrix.to_csv(), media_type="text/csv")

    return {
        "query": matrix.query,
        "generated_at": matrix.generated_at,
        "rows": [r.to_dict() for r in matrix.rows],
        "summary": matrix.summary,
    }


@router.get("/connectors/status")
def connector_status():
    """Return status for all literature connectors."""
    return {
        "connectors": ConnectorRegistry.check_status(),
    }
