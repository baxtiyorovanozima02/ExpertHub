from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.expert import Expert
from app.models.category import Category
from app.models.user import User, UserRole
from app.schemas.expert import ExpertCreate, ExpertUpdate, ExpertOut
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/experts", tags=["experts"])


def _validate_category(db: Session, category_id: int | None) -> None:
    """
    category_id berilgan bo'lsa, u categories jadvalida mavjudligini tekshiradi.
    Aks holda tushunarli 400 xatolik qaytaradi (500 o'rniga).
    """
    if category_id is None:
        return
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=400,
            detail=f"category_id={category_id} bilan kategoriya mavjud emas",
        )


def _get_owned_expert(db: Session, expert_id: int, current_user: User) -> Expert:
    """
    Ekspertni topadi va foydalanuvchi shu profil egasi (yoki admin)
    ekanligini tekshiradi. Aks holda 403/404 qaytaradi.
    """
    expert = db.query(Expert).filter(Expert.id == expert_id).first()
    if not expert:
        raise HTTPException(status_code=404, detail="Ekspert topilmadi")

    if expert.user_id != current_user.id and current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=403,
            detail="Bu ekspert profiliga o'zgartirish kiritish huquqingiz yo'q",
        )
    return expert


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
def create_expert(
    data: ExpertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(Expert).filter(Expert.user_id == current_user.id).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Siz uchun allaqachon ekspert profili yaratilgan",
        )

    _validate_category(db, data.category_id)

    expert = Expert(user_id=current_user.id, **data.model_dump())
    db.add(expert)
    db.commit()
    db.refresh(expert)
    return expert


@router.put("/{expert_id}", response_model=ExpertOut)
def update_expert(
    expert_id: int,
    data: ExpertUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expert = _get_owned_expert(db, expert_id, current_user)

    update_data = data.model_dump(exclude_unset=True)

    update_data.pop("is_verified", None)

    if "category_id" in update_data:
        _validate_category(db, update_data["category_id"])

    for key, value in update_data.items():
        setattr(expert, key, value)
    db.commit()
    db.refresh(expert)
    return expert


@router.delete("/{expert_id}")
def delete_expert(
    expert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expert = _get_owned_expert(db, expert_id, current_user)
    db.delete(expert)
    db.commit()
    return {"message": "Ekspert o'chirildi"}