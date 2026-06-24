"""Performance Determinant endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud
from app.schemas import DeterminantCreate, DeterminantUpdate, DeterminantOut, DeterminantTreeNode

router = APIRouter(prefix="/determinants", tags=["determinants"])


@router.post("/projects/{project_id}", response_model=DeterminantOut, status_code=201)
def create_determinant(project_id: int, data: DeterminantCreate, db: Session = Depends(get_db)):
    return crud.create_determinant(db, project_id, data.model_dump(exclude_unset=True))


@router.get("/projects/{project_id}", response_model=list[DeterminantOut])
def list_determinants(project_id: int, db: Session = Depends(get_db)):
    return crud.get_determinants(db, project_id)


@router.get("/projects/{project_id}/tree", response_model=list[DeterminantTreeNode])
def get_tree(project_id: int, db: Session = Depends(get_db)):
    """Return the full determinant hierarchy as a tree."""
    return crud.get_determinant_tree(db, project_id)


@router.get("/{determinant_id}", response_model=DeterminantOut)
def get_determinant(determinant_id: int, db: Session = Depends(get_db)):
    obj = crud.get_determinant(db, determinant_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Determinant not found")
    return obj


@router.put("/{determinant_id}", response_model=DeterminantOut)
def update_determinant(determinant_id: int, data: DeterminantUpdate, db: Session = Depends(get_db)):
    obj = crud.update_determinant(db, determinant_id, data.model_dump(exclude_unset=True))
    if not obj:
        raise HTTPException(status_code=404, detail="Determinant not found")
    return obj


@router.delete("/{determinant_id}", status_code=204)
def delete_determinant(determinant_id: int, db: Session = Depends(get_db)):
    if not crud.delete_determinant(db, determinant_id):
        raise HTTPException(status_code=404, detail="Determinant not found")
