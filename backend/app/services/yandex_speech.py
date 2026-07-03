# app/services/yandex_speech.py
"""
Yandex SpeechKit orqali Speech-to-Text (STT) va Text-to-Speech (TTS) xizmatlari.

Hujjat: https://cloud.yandex.com/en/docs/speechkit/
Autentifikatsiya: Api-Key (YANDEX_API_KEY), papka: YANDEX_FOLDER_ID.
"""
import httpx
from fastapi import HTTPException

from app.core.config import settings

STT_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
TTS_URL = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"

MAX_STT_FILE_SIZE = 1 * 1024 * 1024  # 1 MB

ALLOWED_TTS_FORMATS = {"oggopus", "lpcm", "mp3"}
DEFAULT_VOICE = "alena"


def _check_credentials() -> None:
    if not settings.YANDEX_API_KEY or not settings.YANDEX_FOLDER_ID:
        raise HTTPException(
            status_code=500,
            detail="Yandex SpeechKit sozlanmagan: YANDEX_API_KEY / YANDEX_FOLDER_ID kerak",
        )


def _auth_headers() -> dict:
    return {"Authorization": f"Api-Key {settings.YANDEX_API_KEY}"}


def speech_to_text(
    audio_bytes: bytes,
    lang: str = "uz-UZ",
    audio_format: str = "oggopus",
    sample_rate_hertz: int = 48000,
) -> str:
    """
    Audio baytlarni matnga aylantiradi (Yandex STT, sinxron/short-audio API).

    :param audio_bytes: audio faylning xom (raw) baytlari (masalan .ogg/.oga - OggOpus,
        yoki .wav - lpcm formatga mos bo'lishi kerak)
    :param lang: tan olish tili, masalan "uz-UZ", "ru-RU", "en-US"
    :param audio_format: "oggopus" (standart) yoki "lpcm"
    :param sample_rate_hertz: faqat format="lpcm" bo'lganda ishlatiladi (8000/16000/48000)
    :return: tan olingan matn
    """
    _check_credentials()

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio fayl bo'sh")

    if len(audio_bytes) > MAX_STT_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=(
                "Audio fayl juda katta (max 1MB, ~30 soniya). "
                "Uzunroq audio uchun boshqa (asinxron) API kerak bo'ladi."
            ),
        )

    params = {
        "folderId": settings.YANDEX_FOLDER_ID,
        "lang": lang,
        "format": audio_format,
    }
    if audio_format == "lpcm":
        params["sampleRateHertz"] = str(sample_rate_hertz)

    try:
        response = httpx.post(
            STT_URL,
            params=params,
            headers=_auth_headers(),
            content=audio_bytes,
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Yandex STT so'roviga ulanib bo'lmadi: {exc}")

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Yandex STT xatolik qaytardi ({response.status_code}): {response.text}",
        )

    data = response.json()
    if data.get("error_code"):
        raise HTTPException(
            status_code=502,
            detail=f"Yandex STT xatolik: {data.get('error_message', data.get('error_code'))}",
        )

    return data.get("result", "")


def text_to_speech(
    text: str,
    lang: str = "uz-UZ",
    voice: str = DEFAULT_VOICE,
    audio_format: str = "oggopus",
    sample_rate_hertz: int = 48000,
    speed: float = 1.0,
) -> bytes:
    """
    Matnni ovozga aylantiradi (Yandex TTS).

    :param text: ovozga aylantiriladigan matn (maksimum 5000 belgi)
    :param lang: til, masalan "uz-UZ", "ru-RU", "en-US"
    :param voice: ovoz nomi (masalan "alena", "filipp", "jane")
    :param audio_format: "oggopus" (standart), "lpcm" yoki "mp3"
    :param sample_rate_hertz: faqat format="lpcm" bo'lganda ishlatiladi
    :param speed: nutq tezligi (0.1 - 3.0 oralig'ida, standart 1.0)
    :return: sintez qilingan audioning xom (raw) baytlari
    """
    _check_credentials()

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Matn bo'sh bo'lishi mumkin emas")

    if len(text) > 5000:
        raise HTTPException(status_code=400, detail="Matn juda uzun (maksimum 5000 belgi)")

    if audio_format not in ALLOWED_TTS_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Noto'g'ri format: {audio_format}. Ruxsat etilganlar: {sorted(ALLOWED_TTS_FORMATS)}",
        )

    data = {
        "text": text,
        "lang": lang,
        "voice": voice,
        "folderId": settings.YANDEX_FOLDER_ID,
        "format": audio_format,
        "speed": str(speed),
    }
    if audio_format == "lpcm":
        data["sampleRateHertz"] = str(sample_rate_hertz)

    try:
        response = httpx.post(
            TTS_URL,
            data=data,
            headers=_auth_headers(),
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Yandex TTS so'roviga ulanib bo'lmadi: {exc}")

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Yandex TTS xatolik qaytardi ({response.status_code}): {response.text}",
        )

    return response.content