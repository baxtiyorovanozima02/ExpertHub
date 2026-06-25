# app/schemas/expert_document.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.expert_document import DocumentFileType


class ExpertDocumentCreate(BaseModel):
    content: str
    source: Optional[str] = None


class ExpertDocumentUpdate(BaseModel):
    content: Optional[str] = None
    source: Optional[str] = None


class ExpertDocumentOut(BaseModel):
    id: int
    expert_id: int
    content: Optional[str] = None
    source: Optional[str] = None
    created_at: datetime
    file_type: DocumentFileType
    original_filename: Optional[str] = None
    file_url: Optional[str] = None
    parse_status: Optional[str] = None
    parse_error: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentStatusOut(BaseModel):
    """
    Fayl qayta ishlash holati — /status va /retry endpointlari uchun.
    """
    id: int
    status: str
    message: str
    filename: Optional[str] = None
    chunk_count: int
    content_length: int
    is_ready: bool
    has_error: bool
    error_detail: Optional[str] = None