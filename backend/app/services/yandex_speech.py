# app/services/yandex_speech.py
"""
Yandex SpeechKit orqali nutqni matnga (STT) va matnni nutqqa (TTS)
aylantiruvchi xizmat qatlami.

Kerakli .env sozlamalari (app/core/config.py da allaqachon mavjud):
    YANDEX_API_KEY   - Yandex Cloud API kaliti (Api-Key ...)
    YANDEX_FOLDER_ID - Yandex Cloud folder ID

Qo'shimcha ixtiyoriy sozlamalar (config.py ga qo'shildi):
    YANDEX_STT_LANG  - tanib olish tili (default: "uz-UZ")
    YANDEX_TTS_LANG  - ovozlashtirish tili (default: "uz-UZ")
    YANDEX_TTS_VOICE - ovoz (default: "madi", uz-UZ uchun mos ovozlardan biri)

Eslatma: Yandex SpeechKit "short audio" recognize endpointi <= 1 daqiqa va
<= 1MB hajmdagi audio uchun mos keladi (Telegram ovozli xabarlar odatda
shu chegaraga to'g'ri keladi va OggOpus formatida keladi, shuning uchun
formatni o'zgartirmasdan to'g'ridan-to'g'ri yuborsa bo'ladi).
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

STT_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
TTS_URL = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"


class YandexSpeechError(Exception):
    """Yandex SpeechKit bilan bog'liq xatoliklar uchun umumiy exception."""


def _auth_header() -> dict:
    if not settings.YANDEX_API_KEY:
        raise YandexSpeechError(
            "YANDEX_API_KEY sozlanmagan. .env faylga YANDEX_API_KEY va "
            "YANDEX_FOLDER_ID qiymatlarini qo'shing."
        )
    return {"Authorization": f"Api-Key {settings.YANDEX_API_KEY}"}


async def speech_to_text(
    audio_bytes: bytes,
    audio_format: str = "oggopus",
    lang: str | None = None,
    sample_rate_hertz: int | None = None,
) -> str:
    """
    Audio baytlarni (ogg/opus, lpcm yoki mp3) matnga aylantiradi.

    audio_format: "oggopus" (Telegram ovozli xabarlar uchun standart),
                  "lpcm" yoki "mp3" ham qo'llab-quvvatlanadi.
    """
    if not audio_bytes:
        raise YandexSpeechError("Audio ma'lumot bo'sh.")

    params = {
        "folderId": settings.YANDEX_FOLDER_ID,
        "lang": lang or settings.YANDEX_STT_LANG,
        "format": audio_format,
    }
    if audio_format == "lpcm" and sample_rate_hertz:
        params["sampleRateHertz"] = str(sample_rate_hertz)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                STT_URL,
                params=params,
                headers=_auth_header(),
                content=audio_bytes,
            )
        except httpx.HTTPError as exc:
            logger.exception("Yandex STT so'roviga ulanishda xatolik")
            raise YandexSpeechError(f"Yandex STT ga ulanib bo'lmadi: {exc}") from exc

    data = response.json()

    if response.status_code != 200 or "result" not in data:
        error_message = data.get("error_message") or data.get("message") or str(data)
        logger.error("Yandex STT xatoligi (%s): %s", response.status_code, error_message)
        raise YandexSpeechError(f"Yandex STT xatoligi: {error_message}")

    return data["result"]


async def text_to_speech(
    text: str,
    voice: str | None = None,
    lang: str | None = None,
    audio_format: str = "oggopus",
    speed: float = 1.0,
) -> bytes:
    """
    Matnni ovozli audio (bytes) ga aylantiradi. Natija OggOpus formatida
    qaytariladi (Telegramga to'g'ridan-to'g'ri voice sifatida yuborish mumkin).
    """
    if not text or not text.strip():
        raise YandexSpeechError("Ovozlashtirish uchun matn bo'sh bo'lmasligi kerak.")

    text = text[:4900]

    data = {
        "text": text,
        "lang": lang or settings.YANDEX_TTS_LANG,
        "voice": voice or settings.YANDEX_TTS_VOICE,
        "format": audio_format,
        "folderId": settings.YANDEX_FOLDER_ID,
        "speed": str(speed),
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(TTS_URL, headers=_auth_header(), data=data)
        except httpx.HTTPError as exc:
            logger.exception("Yandex TTS so'roviga ulanishda xatolik")
            raise YandexSpeechError(f"Yandex TTS ga ulanib bo'lmadi: {exc}") from exc

    if response.status_code != 200:
        try:
            error_message = response.json().get("error_message", response.text)
        except Exception:
            error_message = response.text
        logger.error("Yandex TTS xatoligi (%s): %s", response.status_code, error_message)
        raise YandexSpeechError(f"Yandex TTS xatoligi: {error_message}")

    return response.content