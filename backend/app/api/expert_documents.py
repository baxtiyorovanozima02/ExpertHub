"""
app/api/expert_documents.py
"""

import io
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core import storage
from app.models.expert import Expert
from app.models.expert_document import ExpertDocument, DocumentFileType
from app.models.user import User
from app.schemas.expert_document import ExpertDocumentOut
from app.schemas.expert import ExpertOut
from app.services.auth import get_current_user
from app.ai.tasks import generate_document_embedding_task, parse_and_embed_document_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/expert/documents", tags=["expert_documents"])


_CONTENT_TYPE_MAP = {
    "application/pdf": DocumentFileType.document,
    "application/msword": DocumentFileType.document,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocumentFileType.document,
    "text/plain": DocumentFileType.document,
    "image/jpeg": DocumentFileType.image,
    "image/png": DocumentFileType.image,
    "image/webp": DocumentFileType.image,
    "audio/mpeg": DocumentFileType.audio,
    "audio/mp3": DocumentFileType.audio,
    "audio/wav": DocumentFileType.audio,
    "audio/ogg": DocumentFileType.audio,
    "audio/mp4": DocumentFileType.audio,
}

_MAX_FILE_SIZE = 20 * 1024 * 1024


def _get_current_expert(db: Session, current_user: User) -> Expert:
    expert = db.query(Expert).filter(Expert.user_id == current_user.id).first()
    if not expert:
        raise HTTPException(
            status_code=404,
            detail="Siz ekspert sifatida ro'yxatdan o'tmagansiz"
        )
    return expert


def _with_file_url(document: ExpertDocument) -> ExpertDocumentOut:
    out = ExpertDocumentOut.model_validate(document)
    if document.file_object_name:
        try:
            out.file_url = storage.get_file_url(document.file_object_name)
        except Exception:
            out.file_url = None
    return out


@router.get("/me", response_model=ExpertOut)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Joriy ekspertning profilini qaytaradi."""
    expert = _get_current_expert(db, current_user)
    return expert


@router.get("/", response_model=List[ExpertDocumentOut])
def get_my_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ekspertning barcha hujjatlarini qaytaradi."""
    expert = _get_current_expert(db, current_user)
    documents = (
        db.query(ExpertDocument)
        .filter(ExpertDocument.expert_id == expert.id)
        .order_by(ExpertDocument.id.desc())
        .all()
    )
    return [_with_file_url(doc) for doc in documents]


@router.get("/{document_id}/status")
def get_document_status(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fayl parse holati."""
    expert = _get_current_expert(db, current_user)
    document = db.query(ExpertDocument).filter(
        ExpertDocument.id == document_id,
        ExpertDocument.expert_id == expert.id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Hujjat topilmadi")

    return {
        "id": document.id,
        "parse_status": getattr(document, "parse_status", "unknown"),
        "parse_error": getattr(document, "parse_error", None),
        "has_content": bool(document.content and document.content.strip()),
        "filename": document.original_filename,
    }


@router.post("/upload", response_model=ExpertDocumentOut)
@router.post("/file/", response_model=ExpertDocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    source: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fayl yuklaydi (PDF / rasm / audio / Word / TXT)."""
    expert = _get_current_expert(db, current_user)

    file_type = _CONTENT_TYPE_MAP.get(file.content_type)
    if file_type is None:
        raise HTTPException(
            status_code=400,
            detail=f"Qo'llab-quvvatlanmaydigan fayl turi: {file.content_type}",
        )

    raw_bytes = await file.read()
    if len(raw_bytes) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Fayl hajmi 20 MB dan oshmasligi kerak")
    if len(raw_bytes) == 0:
        raise HTTPException(status_code=400, detail="Bo'sh fayl yuborildi")

    object_name = storage.build_object_name(expert.id, file.filename)
    try:
        storage.upload_file(
            file_obj=io.BytesIO(raw_bytes),
            object_name=object_name,
            length=len(raw_bytes),
            content_type=file.content_type,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    document = ExpertDocument(
        expert_id=expert.id,
        content=None,
        source=source or "file_upload",
        file_type=file_type,
        file_object_name=object_name,
        original_filename=file.filename,
        parse_status="pending",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    parse_and_embed_document_task.delay(document.id)
    logger.info(f"Hujjat #{document.id} parse task ga yuborildi: {file.filename}")

    return _with_file_url(document)


@router.post("/text", response_model=ExpertDocumentOut)
@router.post("/text/", response_model=ExpertDocumentOut)
def add_text_document(
    content: str = Form(...),
    source: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Matnni to'g'ridan-to'g'ri kiritish."""
    if not content.strip():
        raise HTTPException(status_code=400, detail="Matn bo'sh bo'lmasligi kerak")

    expert = _get_current_expert(db, current_user)

    document = ExpertDocument(
        expert_id=expert.id,
        content=content.strip(),
        source=source or "manual_text",
        file_type=DocumentFileType.document,
        file_object_name=None,
        original_filename=None,
        parse_status="done",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    generate_document_embedding_task.delay(document.id)
    return _with_file_url(document)


@router.delete("/{document_id}")
@router.delete("/{document_id}/")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Hujjatni va MinIO dagi faylni o'chiradi."""
    expert = _get_current_expert(db, current_user)
    document = db.query(ExpertDocument).filter(
        ExpertDocument.id == document_id,
        ExpertDocument.expert_id == expert.id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Hujjat topilmadi")

    if document.file_object_name:
        try:
            storage.delete_file(document.file_object_name)
        except Exception as e:
            logger.warning(f"MinIO fayl o'chirishda xato: {e}")

    db.delete(document)
    db.commit()
    return {"message": "Hujjat o'chirildi"}