"""Evidence source and document endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud
from app.schemas import EvidenceSourceCreate, EvidenceSourceOut, DocumentOut

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.post("/projects/{project_id}/sources", response_model=EvidenceSourceOut, status_code=201)
def create_source(project_id: int, data: EvidenceSourceCreate, db: Session = Depends(get_db)):
    return crud.create_evidence_source(db, project_id, data.model_dump(exclude_unset=True))


@router.get("/projects/{project_id}/sources", response_model=list[EvidenceSourceOut])
def list_sources(project_id: int, db: Session = Depends(get_db)):
    return crud.get_evidence_sources(db, project_id)


@router.get("/projects/{project_id}/search")
def search_sources(
    project_id: int,
    q: str = Query(..., description="搜索关键词，支持中文和英文"),
    source_type: Optional[str] = Query(None),
    evidence_level: Optional[str] = Query(None),
    year_from: Optional[int] = Query(None),
    year_to: Optional[int] = Query(None),
    mode: str = Query("hybrid", description="搜索模式: keyword / vector / hybrid"),
    db: Session = Depends(get_db),
):
    """
    Search evidence sources with hybrid keyword + vector search.
    Supports Chinese and English queries.
    """
    from app.agent.search_engine import keyword_search, vector_search, hybrid_search

    if mode == "keyword":
        results = keyword_search(db, q, project_id, source_type, evidence_level, year_from, year_to)
        return {
            "query": q,
            "mode": "keyword",
            "total": len(results),
            "results": [
                {
                    "id": r.id, "title": r.title, "authors": r.authors, "year": r.year,
                    "source_type": r.source_type, "evidence_level": r.evidence_level,
                    "summary": (r.summary or "")[:300], "url": r.url, "doi": r.doi,
                    "relevance": r.relevance, "limitations": r.limitations,
                    "match_type": "关键词匹配", "similarity": None,
                }
                for r in results
            ],
        }

    elif mode == "vector":
        results = vector_search(q, project_id)
        return {
            "query": q,
            "mode": "vector",
            "total": len(results),
            "results": results,
        }

    else:  # hybrid
        return hybrid_search(db, q, project_id)


@router.post("/projects/{project_id}/reindex")
def reindex_sources(project_id: int, db: Session = Depends(get_db)):
    """Rebuild the vector index for all evidence sources in the project."""
    from app.agent.search_engine import index_all_sources
    count = index_all_sources(db, project_id)
    return {"status": "ok", "indexed": count}


@router.post("/projects/{project_id}/documents/upload", status_code=201)
async def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a document. Full text extraction + embedding deferred to Phase 2."""
    from app import models
    content = ""
    try:
        content_bytes = await file.read()
        content = content_bytes.decode("utf-8", errors="replace")
    except Exception:
        content = "(binary file)"

    doc = models.Document(
        project_id=project_id,
        file_name=file.filename or "unknown",
        file_type=file.content_type or "",
        content_text=content[:10000],
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "file_name": doc.file_name, "status": "uploaded"}
