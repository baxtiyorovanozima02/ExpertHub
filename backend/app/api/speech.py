# app/api/speech.py
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import Response

from app.models.user import User
from app.services.auth import get_current_user
from app.services.yandex_speech import speech_to_text, text_to_speech
from app.schemas.speech import SpeechToTextOut, TextToSpeechIn

router = APIRouter(prefix="/api/speech", tags=["speech"])

_CONTENT_TYPES = {
    "oggopus": "audio/ogg",
    "mp3": "audio/mpeg",
    "lpcm": "application/octet-stream",
}


@router.post("/stt", response_model=SpeechToTextOut)
async def recognize_speech(
    file: UploadFile = File(..., description="Audio fayl (.ogg/.oga tavsiya etiladi, max 1MB, ~30s)"),
    lang: str = Form("uz-UZ"),
    format: str = Form("oggopus"),
    sample_rate_hertz: int = Form(48000),
    current_user: User = Depends(get_current_user),
):
    """
    Ovozli xabarni matnga aylantiradi (Yandex SpeechKit STT).
    Frontend/bot ovoz xabarini shu endpointga yuborib, matn qaytarib oladi -
    keyin shu matnni odatiy chat endpointiga (`/api/chat/{id}/message`) yuborish mumkin.
    """
    audio_bytes = await file.read()
    text = speech_to_text(
        audio_bytes,
        lang=lang,
        audio_format=format,
        sample_rate_hertz=sample_rate_hertz,
    )
    return SpeechToTextOut(text=text)


@router.post("/tts")
def synthesize_speech(
    payload: TextToSpeechIn,
    current_user: User = Depends(get_current_user),
):
    """
    Matnni ovozga aylantiradi (Yandex SpeechKit TTS) va audio faylni
    to'g'ridan-to'g'ri (binary) javob sifatida qaytaradi.
    """
    audio_bytes = text_to_speech(
        text=payload.text,
        lang=payload.lang,
        voice=payload.voice,
        audio_format=payload.format,
        speed=payload.speed,
    )
    content_type = _CONTENT_TYPES.get(payload.format, "application/octet-stream")
    extension = {"oggopus": "ogg", "mp3": "mp3", "lpcm": "pcm"}.get(payload.format, "bin")

    return Response(
        content=audio_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="speech.{extension}"'},
    )