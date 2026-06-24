from pydantic import BaseModel
from typing import Optional


class ExpertCreate(BaseModel):
    full_name: str
    category_id: Optional[int] = None
    telegram_id: Optional[int] = None
    bio: Optional[str] = None


class ExpertUpdate(BaseModel):
    full_name: Optional[str] = None
    category_id: Optional[int] = None
    bio: Optional[str] = None
    is_verified: Optional[bool] = None


class ExpertOut(BaseModel):
    id: int
    user_id: int
    full_name: str
    category_id: Optional[int] = None
    telegram_id: Optional[int] = None
    bio: Optional[str] = None
    is_verified: bool

    class Config:
        from_attributes = True