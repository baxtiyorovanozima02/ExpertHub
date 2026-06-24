import uuid
from datetime import timedelta
from typing import BinaryIO, Optional

from minio import Minio
from minio.error import S3Error

from app.core.config import settings

_client: Optional[Minio] = None


def get_client() -> Minio:
    """
    MinIO klientini (singleton) qaytaradi. Birinchi chaqirilganda
    bucket mavjudligini tekshiradi, bo'lmasa yaratadi.
    """
    global _client
    if _client is None:
        _client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        _ensure_bucket(_client)
    return _client


def _ensure_bucket(client: Minio) -> None:
    if not client.bucket_exists(settings.MINIO_BUCKET_NAME):
        client.make_bucket(settings.MINIO_BUCKET_NAME)


def build_object_name(expert_id: int, original_filename: str) -> str:
    """
    Har bir fayl uchun unikal nom hosil qiladi, lekin asl kengaytmasini
    (.pdf, .jpg, .mp3 va h.k.) saqlab qoladi.
    Masalan: experts/7/3f1c9e2a-....pdf
    """
    extension = ""
    if "." in original_filename:
        extension = "." + original_filename.rsplit(".", 1)[-1].lower()
    unique_name = f"{uuid.uuid4().hex}{extension}"
    return f"experts/{expert_id}/{unique_name}"


def upload_file(file_obj: BinaryIO, object_name: str, length: int, content_type: str) -> str:
    """
    Faylni MinIO bucket'iga yuklaydi. `object_name` - bucket ichidagi yo'l
    (build_object_name orqali hosil qilingan). Muvaffaqiyatli bo'lsa
    object_name'ni qaytaradi.
    """
    client = get_client()
    try:
        client.put_object(
            bucket_name=settings.MINIO_BUCKET_NAME,
            object_name=object_name,
            data=file_obj,
            length=length,
            content_type=content_type,
        )
    except S3Error as exc:
        raise RuntimeError(f"MinIO'ga fayl yuklashda xatolik: {exc}")
    return object_name


def get_file_url(object_name: str, expires_minutes: int = 60) -> str:
    """
    Faylga vaqtinchalik (presigned) URL beradi - to'g'ridan-to'g'ri ochish
    yoki yuklab olish uchun. Bucket public bo'lmagani uchun bu kerak.
    """
    client = get_client()
    return client.presigned_get_object(
        settings.MINIO_BUCKET_NAME,
        object_name,
        expires=timedelta(minutes=expires_minutes),
    )


def delete_file(object_name: str) -> None:
    client = get_client()
    try:
        client.remove_object(settings.MINIO_BUCKET_NAME, object_name)
    except S3Error:
        pass