"""Report endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud
from app.schemas import ReportOut, ReportGenerateRequest
from app.agent.report_generator import generate_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/projects/{project_id}/generate", response_model=ReportOut, status_code=201)
def generate_project_report(project_id: int, req: ReportGenerateRequest, db: Session = Depends(get_db)):
    """Generate a report for a project."""
    report = generate_report(db, project_id, req.report_type, req.athlete_id, req.extra_notes)
    if not report:
        raise HTTPException(status_code=400, detail="Failed to generate report")
    return report


@router.get("/projects/{project_id}", response_model=list[ReportOut])
def list_reports(project_id: int, db: Session = Depends(get_db)):
    return crud.get_reports(db, project_id)


@router.get("/{report_id}", response_model=ReportOut)
def get_report(report_id: int, db: Session = Depends(get_db)):
    obj = crud.get_report(db, report_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Report not found")
    return obj
