"""
app/ai/file_parser.py

Fayl turlariga qarab matn chiqaradi:
  - PDF      → pdfplumber orqali
  - Rasm     → pytesseract (OCR) orqali
  - Audio    → faster-whisper (lokal, bepul) orqali
"""

import io
import logging
import tempfile
import os
from typing import Optional

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber o'rnatilmagan: pip install pdfplumber")

    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text.strip())

    result = "\n\n".join(text_parts)
    if not result.strip():
        raise ValueError("PDF dan matn topilmadi (skanerlangan rasm bo'lishi mumkin)")
    return result


def extract_text_from_image(file_bytes: bytes) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise RuntimeError(
            "pytesseract yoki Pillow o'rnatilmagan: pip install pytesseract Pillow"
        )

    image = Image.open(io.BytesIO(file_bytes))
    text = pytesseract.image_to_string(image, lang="uzb+rus+eng")
    if not text.strip():
        raise ValueError("Rasmdan matn topilmadi")
    return text.strip()


_whisper_model = None


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError(
                "faster-whisper o'rnatilmagan: pip install faster-whisper"
            )
        logger.info("faster-whisper 'base' modeli yuklanmoqda...")
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info("faster-whisper modeli tayyor.")
    return _whisper_model


def extract_text_from_audio(file_bytes: bytes, filename: str = "audio.mp3") -> str:
    ext = os.path.splitext(filename)[-1].lower() or ".mp3"

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        model = _get_whisper_model()
        segments, info = model.transcribe(tmp_path, beam_size=5)
        text = " ".join(segment.text for segment in segments).strip()
        if not text:
            raise ValueError("Audio dan matn topilmadi")
        logger.info(f"Audio til: {info.language}, davomiylik: {info.duration:.1f}s")
        return text
    finally:
        os.unlink(tmp_path)


def parse_file(
    file_bytes: bytes,
    content_type: str,
    filename: Optional[str] = None,
) -> str:
    ct = content_type.lower()

    if ct == "application/pdf":
        logger.info(f"PDF parsing: {filename}")
        return extract_text_from_pdf(file_bytes)

    elif ct == "text/plain":
        logger.info(f"Plain text: {filename}")
        return file_bytes.decode("utf-8", errors="replace")

    elif ct in (
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ):
        try:
            import docx as python_docx
        except ImportError:
            raise RuntimeError("python-docx o'rnatilmagan: pip install python-docx")
        doc = python_docx.Document(io.BytesIO(file_bytes))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        if not text:
            raise ValueError("Word hujjatidan matn topilmadi")
        return text

    elif ct.startswith("image/"):
        logger.info(f"OCR (rasm): {filename}")
        return extract_text_from_image(file_bytes)

    elif ct.startswith("audio/"):
        logger.info(f"STT (audio): {filename}")
        return extract_text_from_audio(file_bytes, filename or "audio.mp3")

    else:
        raise ValueError(f"Qo'llab-quvvatlanmaydigan fayl turi: {content_type}")