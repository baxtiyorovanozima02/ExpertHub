# app/ai/tasks.py
"""
Celery tasklar — parse_status yangilanishi qo'shildi.

Har bir bosqichda parse_status yangilanadi:
  pending -> parsing -> chunking -> embedding -> done
                                              -> error

Bu holat /status va /status/stream endpointlari orqali
frontend ga real-time uzatiladi.
"""

from celery_worker import celery_app
from app.core.database import SessionLocal
from app.models.expert_document import ExpertDocument
from app.models.document_chunk import DocumentChunk
from app.models.expert import Expert
from app.ai.embeddings import generate_embedding
from app.ai.chunking import split_text_into_chunks
from app.ai import qdrant_client

import logging

logger = logging.getLogger(__name__)


def _set_status(db, document: ExpertDocument, status: str, error: str = None):
    """Hujjat statusini yangilash — bir joyda, xatosiz."""
    document.parse_status = status
    if error is not None:
        document.parse_error = error[:500]
    db.commit()


def _embed_document(db, document_id: int, category_id):
    """
    Hujjatni chunklaydi va Qdrant ga saqlaydi.
    Har bir bosqichda parse_status yangilanadi.
    """
    document = db.query(ExpertDocument).filter(ExpertDocument.id == document_id).first()
    if not document or not document.content:
        return 0

    _set_status(db, document, "chunking")

    old_chunks = db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    ).all()
    for old_chunk in old_chunks:
        qdrant_client.delete_chunk_embedding(old_chunk.id)
        db.delete(old_chunk)
    db.commit()
    qdrant_client.delete_document_centroid(document_id)

    chunk_texts = split_text_into_chunks(document.content)
    if not chunk_texts:
        return 0

    _set_status(db, document, "embedding")

    count = 0
    chunk_vectors = []
    for index, chunk_text in enumerate(chunk_texts):
        chunk = DocumentChunk(
            document_id=document.id,
            chunk_index=index,
            content=chunk_text,
        )
        db.add(chunk)
        db.commit()
        db.refresh(chunk)

        vector = generate_embedding(chunk_text)
        chunk_vectors.append(vector)
        qdrant_client.upsert_chunk_embedding(
            chunk_id=chunk.id,
            vector=vector,
            document_id=document.id,
            category_id=category_id,
        )
        count += 1

    if chunk_vectors:
        qdrant_client.upsert_document_centroid(
            document_id=document.id,
            chunk_vectors=chunk_vectors,
            category_id=category_id,
        )

    return count


@celery_app.task(name="generate_document_embedding")
def generate_document_embedding_task(document_id: int):
    """
    Hujjat content i allaqachon to'ldirilgan bo'lsa
    (masalan, matn orqali kiritilgan), to'g'ridan-to'g'ri
    chunk + embed qiladi.
    """
    db = SessionLocal()
    try:
        document = db.query(ExpertDocument).filter(
            ExpertDocument.id == document_id
        ).first()
        if not document:
            return f"Hujjat #{document_id} topilmadi"

        expert = db.query(Expert).filter(Expert.id == document.expert_id).first()
        category_id = expert.category_id if expert else None

        count = _embed_document(db, document_id, category_id)

        _set_status(db, document, "done")
        return f"Hujjat #{document_id} uchun {count} ta chunk va embedding saqlandi"

    except Exception as exc:
        logger.error(f"Hujjat #{document_id} embedding xatosi: {exc}")
        try:
            document = db.query(ExpertDocument).filter(
                ExpertDocument.id == document_id
            ).first()
            if document:
                _set_status(db, document, "error", str(exc))
        except Exception:
            pass
        raise
    finally:
        db.close()


@celery_app.task(name="parse_and_embed_document", bind=True, max_retries=2)
def parse_and_embed_document_task(self, document_id: int):
    """
    1. MinIO dan faylni yuklab oladi         -> status: parsing
    2. Fayl turiga qarab matn chiqaradi
    3. Chiqarilgan matnni DBga saqlaydi
    4. Chunk + embed qiladi                  -> status: chunking -> embedding
    5. Yakunlaydi                            -> status: done | error
    """
    from app.core import storage
    from app.ai.file_parser import parse_file

    db = SessionLocal()
    try:
        document = db.query(ExpertDocument).filter(
            ExpertDocument.id == document_id
        ).first()
        if not document:
            return f"Hujjat #{document_id} topilmadi"

        if not document.file_object_name:
            return f"Hujjat #{document_id} da fayl yo'q"

        if document.content and document.content.strip():
            logger.info(f"Hujjat #{document_id} allaqachon parse qilingan, o'tkazildi")
            return f"Hujjat #{document_id} allaqachon matn bor"

        _set_status(db, document, "parsing")

        logger.info(f"MinIO dan yuklanmoqda: {document.file_object_name}")
        minio_client = storage.get_client()
        from app.core.config import settings

        response = minio_client.get_object(
            settings.MINIO_BUCKET_NAME,
            document.file_object_name,
        )
        file_bytes = response.read()
        response.close()
        response.release_conn()

        filename = document.original_filename or "file"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        ext_to_ct = {
            "pdf":   "application/pdf",
            "txt":   "text/plain",
            "md":    "text/markdown",
            "log":   "text/plain",
            "doc":   "application/msword",
            "docx":  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xls":   "application/vnd.ms-excel",
            "xlsx":  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "csv":   "text/csv",
            "tsv":   "text/tab-separated-values",
            "ppt":   "application/vnd.ms-powerpoint",
            "pptx":  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "epub":  "application/epub+zip",
            "html":  "text/html",
            "htm":   "text/html",
            "xhtml": "application/xhtml+xml",
            "xml":   "application/xml",
            "json":  "application/json",
            "jsonl": "application/x-ndjson",
            "rtf":   "application/rtf",
            "jpg":   "image/jpeg",
            "jpeg":  "image/jpeg",
            "png":   "image/png",
            "webp":  "image/webp",
            "gif":   "image/gif",
            "tiff":  "image/tiff",
            "bmp":   "image/bmp",
            "mp3":   "audio/mpeg",
            "wav":   "audio/wav",
            "ogg":   "audio/ogg",
            "m4a":   "audio/mp4",
            "aac":   "audio/aac",
            "flac":  "audio/flac",
            "weba":  "audio/webm",
        }
        detected_ct = ext_to_ct.get(ext, "application/octet-stream")

        logger.info(f"Parsing: {filename} ({detected_ct})")
        extracted_text = parse_file(file_bytes, detected_ct, filename)

        document.content = extracted_text
        db.commit()
        logger.info(f"Hujjat #{document_id}: {len(extracted_text)} belgi chiqarildi")

        expert = db.query(Expert).filter(Expert.id == document.expert_id).first()
        category_id = expert.category_id if expert else None

        count = _embed_document(db, document_id, category_id)

        _set_status(db, document, "done")
        return (
            f"Hujjat #{document_id}: matn chiqarildi ({len(extracted_text)} belgi), "
            f"{count} ta chunk saqlandi"
        )

    except Exception as exc:
        logger.error(f"Hujjat #{document_id} parse xatosi: {exc}")
        try:
            document = db.query(ExpertDocument).filter(
                ExpertDocument.id == document_id
            ).first()
            if document:
                _set_status(db, document, "error", str(exc))
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()