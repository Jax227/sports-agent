"""KPI endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud
from app.schemas import (
    KPICreate, KPIUpdate, KPIOut, KPITrendOut,
    MeasurementCreate, MeasurementOut,
)

router = APIRouter(prefix="/kpis", tags=["kpis"])


# ── KPI CRUD ───────────────────────────────────────────────────

@router.post("/projects/{project_id}", response_model=KPIOut, status_code=201)
def create_kpi(project_id: int, data: KPICreate, db: Session = Depends(get_db)):
    return crud.create_kpi(db, project_id, data.model_dump(exclude_unset=True))


@router.get("/projects/{project_id}", response_model=list[KPIOut])
def list_kpis(project_id: int, db: Session = Depends(get_db)):
    return crud.get_kpis(db, project_id)


@router.get("/{kpi_id}", response_model=KPIOut)
def get_kpi(kpi_id: int, db: Session = Depends(get_db)):
    obj = crud.get_kpi(db, kpi_id)
    if not obj:
        raise HTTPException(status_code=404, detail="KPI not found")
    return obj


@router.put("/{kpi_id}", response_model=KPIOut)
def update_kpi(kpi_id: int, data: KPIUpdate, db: Session = Depends(get_db)):
    obj = crud.update_kpi(db, kpi_id, data.model_dump(exclude_unset=True))
    if not obj:
        raise HTTPException(status_code=404, detail="KPI not found")
    return obj


@router.delete("/{kpi_id}", status_code=204)
def delete_kpi(kpi_id: int, db: Session = Depends(get_db)):
    if not crud.delete_kpi(db, kpi_id):
        raise HTTPException(status_code=404, detail="KPI not found")


# ── Measurements ───────────────────────────────────────────────

@router.post("/{kpi_id}/measurements", response_model=MeasurementOut, status_code=201)
def add_measurement(kpi_id: int, data: MeasurementCreate, db: Session = Depends(get_db)):
    payload = data.model_dump(exclude_unset=True)
    payload["kpi_id"] = kpi_id
    return crud.create_measurement(db, payload)


@router.get("/{kpi_id}/measurements", response_model=list[MeasurementOut])
def list_measurements(
    kpi_id: int,
    athlete_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    return crud.get_measurements(db, kpi_id, athlete_id)


@router.get("/{kpi_id}/trend", response_model=KPITrendOut)
def get_trend(
    kpi_id: int,
    athlete_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    result = crud.get_kpi_trend(db, kpi_id, athlete_id)
    if not result:
        raise HTTPException(status_code=404, detail="KPI not found")
    return result
