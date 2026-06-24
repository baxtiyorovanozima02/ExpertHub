from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.expert import Expert
from app.schemas.expert import ExpertCreate, ExpertUpdate, ExpertOut

router = APIRouter(prefix="/api/experts", tags=["experts"])


@router.get("/", response_model=List[ExpertOut])
def get_experts(db: Session = Depends(get_db)):
    return db.query(Expert).all()


@router.get("/{expert_id}", response_model=ExpertOut)
def get_expert(expert_id: int, db: Session = Depends(get_db)):
    expert = db.query(Expert).filter(Expert.id == expert_id).first()
    if not expert:
        raise HTTPException(status_code=404, detail="Ekspert topilmadi")
    return expert


@router.post("/", response_model=ExpertOut)
def create_expert(data: ExpertCreate, db: Session = Depends(get_db)):
    expert = Expert(user_id=1, **data.model_dump())
    db.add(expert)
    db.commit()
    db.refresh(expert)
    return expert


@router.put("/{expert_id}", response_model=ExpertOut)
def update_expert(expert_id: int, data: ExpertUpdate, db: Session = Depends(get_db)):
    expert = db.query(Expert).filter(Expert.id == expert_id).first()
    if not expert:
        raise HTTPException(status_code=404, detail="Ekspert topilmadi")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(expert, key, value)
    db.commit()
    db.refresh(expert)
    return expert


@router.delete("/{expert_id}")
def delete_expert(expert_id: int, db: Session = Depends(get_db)):
    expert = db.query(Expert).filter(Expert.id == expert_id).first()
    if not expert:
        raise HTTPException(status_code=404, detail="Ekspert topilmadi")
    db.delete(expert)
    db.commit()
    return {"message": "Ekspert o'chirildi"}