from pydantic import BaseModel
from typing import Optional


class CategoryCreate(BaseModel):
    name: str
    icon: Optional[str] = None
    description: Optional[str] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None


class CategoryOut(BaseModel):
    id: int
    name: str
    icon: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True