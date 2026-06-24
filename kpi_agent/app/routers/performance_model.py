"""
Performance Model endpoints: literature extraction → determinant hierarchy.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import PMExtractRequest, PMCandidateUpdate, PMSaveRequest
from app.performance_model.pipeline import run_full_pipeline, save_model_to_db
from app.performance_model.batch_loader import get_cached_queries, load_literature_batch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/performance-model", tags=["performance-model"])


@router.post("/extract-from-literature")
def extract_from_literature(data: PMExtractRequest):
    """Run the full Literature → Performance Model extraction pipeline.

    Loads cached literature results, extracts determinant candidates,
    merges duplicates, and builds a hierarchical model tree.
    """
    try:
        result = run_full_pipeline(
            query_id=data.query_id,
            literature_ids=data.literature_ids,
            limit=data.limit,
            include_fulltext=data.include_fulltext,
            use_keybert=data.use_keybert,
            use_yake=data.use_yake,
            use_spacy=data.use_spacy,
            min_confidence=data.min_confidence,
        )
        return result
    except Exception as e:
        logger.error(f"Extraction pipeline error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/candidates")
def list_candidates(
    query_id: Optional[int] = Query(None),
    limit: int = Query(50),
    min_confidence: float = Query(0.1),
):
    """Run extraction and return candidate list (lightweight, no full pipeline)."""
    try:
        result = run_full_pipeline(
            query_id=query_id,
            limit=limit,
            min_confidence=min_confidence,
            use_keybert=False,
            use_yake=False,
            use_spacy=False,
            include_fulltext=False,
        )
        return {
            "candidates": result.get("candidates", []),
            "candidates_merged": result.get("candidates_merged", 0),
            "documents_loaded": result.get("documents_loaded", 0),
        }
    except Exception as e:
        logger.error(f"List candidates error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tree")
def get_model_tree(
    query_id: Optional[int] = Query(None),
    literature_ids: Optional[str] = Query(None),
    limit: int = Query(50),
):
    """Generate and return the performance model tree."""
    try:
        lit_ids = None
        if literature_ids:
            lit_ids = [int(x) for x in literature_ids.split(",") if x.strip()]
        result = run_full_pipeline(
            query_id=query_id,
            literature_ids=lit_ids,
            limit=limit,
        )
        return {
            "model_tree": result.get("model_tree", {}),
            "candidates_merged": result.get("candidates_merged", 0),
            "documents_loaded": result.get("documents_loaded", 0),
        }
    except Exception as e:
        logger.error(f"Get model tree error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queries")
def list_queries():
    """Get all cached literature search queries."""
    try:
        queries = get_cached_queries()
        return {"queries": queries, "total": len(queries)}
    except Exception as e:
        logger.error(f"List queries error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export")
def export_model(
    query_id: Optional[int] = Query(None),
    literature_ids: Optional[str] = Query(None),
    limit: int = Query(50),
    format: str = Query("json"),
):
    """Export the performance model in JSON, CSV, or Markdown format."""
    try:
        lit_ids = None
        if literature_ids:
            lit_ids = [int(x) for x in literature_ids.split(",") if x.strip()]
        result = run_full_pipeline(
            query_id=query_id,
            literature_ids=lit_ids,
            limit=limit,
        )

        if format == "markdown":
            return {"content": result.get("evidence_report", "")}
        elif format == "csv":
            import csv, io
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["canonical_name", "category", "display_name_en", "evidence_count",
                              "confidence_score", "evidence_strength_score"])
            for c in result.get("candidates", []):
                writer.writerow([
                    c.get("canonical_name", ""),
                    c.get("category_key", ""),
                    c.get("display_name_en", ""),
                    len(c.get("source_literature_ids", [])),
                    c.get("confidence_score", 0),
                    c.get("evidence_strength_score", 0),
                ])
            return {"content": output.getvalue()}
        else:
            return {
                "model_tree": result.get("model_tree", {}),
                "candidates": result.get("candidates", []),
                "evidence_links": result.get("evidence_links_data", []),
            }
    except Exception as e:
        logger.error(f"Export model error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
def get_literature_documents(
    query_id: Optional[int] = Query(None),
    limit: int = Query(100),
):
    """Get cached literature documents for review."""
    try:
        docs = load_literature_batch(query_id=query_id, limit=limit, include_fulltext=False)
        return {
            "documents": [
                {
                    "literature_id": d.literature_id,
                    "title": d.title[:200],
                    "year": d.year,
                    "doi": d.doi,
                    "has_abstract": bool(d.abstract),
                    "has_fulltext": d.fulltext_available,
                    "source_databases": d.source_databases,
                    "ranking_score": d.ranking_score,
                }
                for d in docs
            ],
            "total": len(docs),
        }
    except Exception as e:
        logger.error(f"Get documents error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save-to-project")
def save_to_project(data: PMSaveRequest, db: Session = Depends(get_db)):
    """Save the extracted performance model as PerformanceDeterminant records."""
    try:
        pipeline_result = {
            "candidates": data.candidates,
            "evidence_links_data": data.evidence_links,
        }
        created = save_model_to_db(pipeline_result, data.project_id, db)
        return {"status": "ok", "created": created}
    except Exception as e:
        logger.error(f"Save to project error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
