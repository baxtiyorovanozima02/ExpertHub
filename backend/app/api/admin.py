from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.expert import Expert
from app.models.user import User, UserRole
from app.models.category import Category
from app.models.expert_document import ExpertDocument
from app.schemas.expert import ExpertOut
from app.schemas.admin import AdminStatsOut
from app.services.auth import require_role

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/experts/", response_model=List[ExpertOut])
def list_experts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    return db.query(Expert).all()


@router.put("/experts/{expert_id}/verify/", response_model=ExpertOut)
def verify_expert(
    expert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    expert = db.query(Expert).filter(Expert.id == expert_id).first()
    if not expert:
        raise HTTPException(status_code=404, detail="Ekspert topilmadi")
    expert.is_verified = True
    db.commit()
    db.refresh(expert)
    return expert


@router.get("/stats/", response_model=AdminStatsOut)
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    return AdminStatsOut(
        total_users=db.query(User).count(),
        total_experts=db.query(Expert).count(),
        verified_experts=db.query(Expert).filter(Expert.is_verified == True).count(),
        total_categories=db.query(Category).count(),
        total_documents=db.query(ExpertDocument).count(),
    )