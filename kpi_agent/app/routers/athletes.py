"""Athlete endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud
from app.schemas import AthleteCreate, AthleteUpdate, AthleteOut, AthleteDashboardOut

router = APIRouter(prefix="/athletes", tags=["athletes"])


@router.post("/projects/{project_id}", response_model=AthleteOut, status_code=201)
def create_athlete(project_id: int, data: AthleteCreate, db: Session = Depends(get_db)):
    return crud.create_athlete(db, project_id, data.model_dump(exclude_unset=True))


@router.get("/projects/{project_id}", response_model=list[AthleteOut])
def list_athletes(project_id: int, db: Session = Depends(get_db)):
    return crud.get_athletes(db, project_id)


@router.get("/{athlete_id}", response_model=AthleteOut)
def get_athlete(athlete_id: int, db: Session = Depends(get_db)):
    obj = crud.get_athlete(db, athlete_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Athlete not found")
    return obj


@router.put("/{athlete_id}", response_model=AthleteOut)
def update_athlete(athlete_id: int, data: AthleteUpdate, db: Session = Depends(get_db)):
    obj = crud.update_athlete(db, athlete_id, data.model_dump(exclude_unset=True))
    if not obj:
        raise HTTPException(status_code=404, detail="Athlete not found")
    return obj


@router.get("/{athlete_id}/dashboard", response_model=AthleteDashboardOut)
def athlete_dashboard(athlete_id: int, db: Session = Depends(get_db)):
    result = crud.get_athlete_dashboard(db, athlete_id)
    if not result:
        raise HTTPException(status_code=404, detail="Athlete not found")
    return result
