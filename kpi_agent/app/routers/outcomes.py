"""Performance Outcome endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud
from app.schemas import OutcomeCreate, OutcomeUpdate, OutcomeOut

router = APIRouter(prefix="/outcomes", tags=["outcomes"])


@router.post("/projects/{project_id}", response_model=OutcomeOut, status_code=201)
def create_outcome(project_id: int, data: OutcomeCreate, db: Session = Depends(get_db)):
    return crud.create_outcome(db, project_id, data.model_dump(exclude_unset=True))


@router.get("/projects/{project_id}", response_model=list[OutcomeOut])
def list_outcomes(project_id: int, db: Session = Depends(get_db)):
    return crud.get_outcomes(db, project_id)


@router.get("/{outcome_id}", response_model=OutcomeOut)
def get_outcome(outcome_id: int, db: Session = Depends(get_db)):
    obj = crud.get_outcome(db, outcome_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Outcome not found")
    return obj


@router.put("/{outcome_id}", response_model=OutcomeOut)
def update_outcome(outcome_id: int, data: OutcomeUpdate, db: Session = Depends(get_db)):
    obj = crud.update_outcome(db, outcome_id, data.model_dump(exclude_unset=True))
    if not obj:
        raise HTTPException(status_code=404, detail="Outcome not found")
    return obj


@router.delete("/{outcome_id}", status_code=204)
def delete_outcome(outcome_id: int, db: Session = Depends(get_db)):
    if not crud.delete_outcome(db, outcome_id):
        raise HTTPException(status_code=404, detail="Outcome not found")
