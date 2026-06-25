# app/api/expert_documents.py
"""
Expert Documents API

Qo'shilgan yaxshilanishlar:
  - GET /{id}/status     — kengaytirilgan status (chunk soni, fayl hajmi, qayta urinish)
  - GET /{id}/status/stream — SSE orqali real-time progress
"""

import io
import logging
import asyncio
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import json

from app.core.database import get_db
from app.core import storage
from app.models.expert import Expert
from app.models.expert_document import ExpertDocument, DocumentFileType
from app.models.document_chunk import DocumentChunk
from app.models.user import User
from app.schemas.expert_document import ExpertDocumentOut, DocumentStatusOut
from app.schemas.expert import ExpertOut
from app.services.auth import get_current_user
from app.ai.tasks import generate_document_embedding_task, parse_and_embed_document_task
from app.ai import qdrant_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/expert/documents", tags=["expert_documents"])


_CONTENT_TYPE_MAP = {
    "application/pdf":                                                              DocumentFileType.document,
    "application/msword":                                                           DocumentFileType.document,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":     DocumentFileType.document,
    "text/plain":                                                                   DocumentFileType.document,
    "text/markdown":                                                                DocumentFileType.document,
    "text/x-markdown":                                                              DocumentFileType.document,
    "application/vnd.ms-excel":                                                     DocumentFileType.document,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":           DocumentFileType.document,
    "text/csv":                                                                     DocumentFileType.document,
    "application/csv":                                                              DocumentFileType.document,
    "text/tab-separated-values":                                                    DocumentFileType.document,
    "application/vnd.ms-powerpoint":                                                DocumentFileType.document,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation":   DocumentFileType.document,
    "application/epub+zip":                                                         DocumentFileType.document,
    "text/html":                                                                    DocumentFileType.document,
    "application/xhtml+xml":                                                        DocumentFileType.document,
    "application/xml":                                                              DocumentFileType.document,
    "text/xml":                                                                     DocumentFileType.document,
    "application/json":                                                             DocumentFileType.document,
    "application/x-ndjson":                                                        DocumentFileType.document,
    "application/jsonlines":                                                        DocumentFileType.document,
    "text/json":                                                                    DocumentFileType.document,
    "application/rtf":                                                              DocumentFileType.document,
    "text/rtf":                                                                     DocumentFileType.document,
    "image/jpeg":  DocumentFileType.image,
    "image/png":   DocumentFileType.image,
    "image/webp":  DocumentFileType.image,
    "image/gif":   DocumentFileType.image,
    "image/tiff":  DocumentFileType.image,
    "image/bmp":   DocumentFileType.image,
    "audio/mpeg":  DocumentFileType.audio,
    "audio/mp3":   DocumentFileType.audio,
    "audio/wav":   DocumentFileType.audio,
    "audio/ogg":   DocumentFileType.audio,
    "audio/mp4":   DocumentFileType.audio,
    "audio/aac":   DocumentFileType.audio,
    "audio/flac":  DocumentFileType.audio,
    "audio/webm":  DocumentFileType.audio,
}

_STATUS_MESSAGES = {
    "pending":    "Navbatda kutilmoqda...",
    "parsing":    "Fayl o'qilmoqda...",
    "chunking":   "Matn bo'laklarga bo'linmoqda...",
    "embedding":  "AI embedding yaratilmoqda...",
    "done":       "Tayyor! Hujjat qidiruv uchun faol.",
    "error":      "Xato yuz berdi.",
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


def _build_status(document: ExpertDocument, db: Session) -> dict:
    """
    Hujjat holati haqida to'liq ma'lumot yig'adi.
    Polling va SSE ikkalasida ishlatiladi.
    """
    status = document.parse_status or "pending"
    chunk_count = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document.id)
        .count()
    )
    content_length = len(document.content) if document.content else 0

    return {
        "id":             document.id,
        "status":         status,
        "message":        _STATUS_MESSAGES.get(status, status),
        "filename":       document.original_filename,
        "chunk_count":    chunk_count,
        "content_length": content_length,
        "is_ready":       status == "done",
        "has_error":      status == "error",
        "error_detail":   document.parse_error if status == "error" else None,
    }



@router.get("/me", response_model=ExpertOut)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expert = _get_current_expert(db, current_user)
    return expert


@router.get("/", response_model=List[ExpertDocumentOut])
def get_my_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expert = _get_current_expert(db, current_user)
    documents = (
        db.query(ExpertDocument)
        .filter(ExpertDocument.expert_id == expert.id)
        .order_by(ExpertDocument.id.desc())
        .all()
    )
    return [_with_file_url(doc) for doc in documents]



@router.get("/{document_id}/status", response_model=DocumentStatusOut)
def get_document_status(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fayl qayta ishlash holati — polling uchun.

    Frontend har 2-3 soniyada shu endpointga murojaat qilib
    progress bar yoki status badge yangilaydi.

    Response:
        status:         pending | parsing | chunking | embedding | done | error
        message:        User-friendly o'zbek tili xabari
        chunk_count:    Nechta bo'lak yaratildi (done bo'lganda)
        content_length: Nechta belgi matn chiqarildi
        is_ready:       true bo'lsa — hujjat qidiruvga tayyor
        has_error:      true bo'lsa — error_detail ni ko'rsat
        error_detail:   Xato matni (faqat has_error=true da)
    """
    expert = _get_current_expert(db, current_user)
    document = db.query(ExpertDocument).filter(
        ExpertDocument.id == document_id,
        ExpertDocument.expert_id == expert.id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Hujjat topilmadi")

    return _build_status(document, db)



@router.get("/{document_id}/status/stream")
async def stream_document_status(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Real-time fayl qayta ishlash holati — Server-Sent Events orqali.

    Fayl yuklanishi bilanoq frontend shu endpointga ulanadi va
    hech qanday polling qilmasdan avtomatik yangilanishlarni oladi.
    done yoki error holati kelganda stream avtomatik yopiladi.

    SSE formatida keladi:
        event: status
        data: {"status": "parsing", "message": "Fayl o'qilmoqda...", ...}

        event: status
        data: {"status": "done", "chunk_count": 24, "is_ready": true, ...}

    Frontend ulash misoli (JavaScript):
        const es = new EventSource(`/api/expert/documents/${id}/status/stream`);
        es.addEventListener('status', e => {
            const data = JSON.parse(e.data);
            updateProgressBar(data);
            if (data.is_ready || data.has_error) es.close();
        });
    """
    expert = _get_current_expert(db, current_user)
    document = db.query(ExpertDocument).filter(
        ExpertDocument.id == document_id,
        ExpertDocument.expert_id == expert.id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Hujjat topilmadi")

    async def event_generator():
        max_wait_seconds = 600
        poll_interval   = 2.0
        elapsed         = 0
        last_status     = None

        while elapsed < max_wait_seconds:
            db.expire(document)
            db.refresh(document)

            status_data = _build_status(document, db)
            current_status = status_data["status"]

            if current_status != last_status:
                payload = json.dumps(status_data, ensure_ascii=False)
                yield f"event: status\ndata: {payload}\n\n"
                last_status = current_status

            if current_status in ("done", "error"):
                break

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        if last_status not in ("done", "error"):
            timeout_data = {
                **_build_status(document, db),
                "status":  "error",
                "message": "Kutish vaqti tugadi. Sahifani yangilang.",
                "has_error": True,
            }
            yield f"event: status\ndata: {json.dumps(timeout_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "Connection":       "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )



@router.post("/{document_id}/retry", response_model=DocumentStatusOut)
def retry_document_processing(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Xato bo'lgan hujjatni qayta parse qiladi.
    Faqat status=error bo'lgan hujjatlarda ishlaydi.
    """
    expert = _get_current_expert(db, current_user)
    document = db.query(ExpertDocument).filter(
        ExpertDocument.id == document_id,
        ExpertDocument.expert_id == expert.id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Hujjat topilmadi")

    if document.parse_status not in ("error", "pending"):
        raise HTTPException(
            status_code=400,
            detail=f"Faqat xato yoki kutishdagi hujjatlarni qayta ishga tushirish mumkin. "
                   f"Joriy holat: {document.parse_status}"
        )

    document.parse_status = "pending"
    document.parse_error  = None
    document.content      = None
    db.commit()

    if document.file_object_name:
        parse_and_embed_document_task.delay(document.id)
    else:
        generate_document_embedding_task.delay(document.id)

    logger.info(f"Hujjat #{document_id} qayta ishga tushirildi.")
    return _build_status(document, db)



@router.post("/upload", response_model=ExpertDocumentOut)
@router.post("/file/", response_model=ExpertDocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    source: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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

    try:
        qdrant_client.delete_document_centroid(document.id)
    except Exception as e:
        logger.warning(f"Qdrant centroid o'chirishda xato: {e}")

    db.delete(document)
    db.commit()
    return {"message": "Hujjat o'chirildi"}