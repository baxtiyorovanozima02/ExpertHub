"""
Yandex SpeechKit orqali nutqni matnga (STT) va matnni nutqqa (TTS)
aylantiruvchi xizmat qatlami.

MUHIM (v1 vs v3):
    - STT (speech_to_text) - Yandex SpeechKit **API v1** REST endpointidan
      foydalanadi (stt.api.cloud.yandex.net/speech/v1/stt:recognize).
      "uz-UZ" tili bu API'da rasman qo'llab-quvvatlanadi, shuning uchun bu
      qism o'zgarishsiz qoldirilgan.

    - TTS (text_to_speech) - avval **API v1**ga (tts.api.cloud.yandex.net/
      speech/v1/tts:synthesize) murojaat qilar edi, lekin bu eski endpoint
      FAQAT ru-RU, en-US va tr-TR tillarini qo'llab-quvvatlaydi - "uz-UZ"
      bu yerda ishlamaydi. Yandex o'zbek tilini TTS uchun faqat yangi
      **API v3** (gRPC) orqali qo'shgan, ovoz nomi "nigora" (ayol ovozi).
      Shuning uchun bu funksiya endi API v3 gRPC orqali ishlaydi.
      API v3'da til alohida parametr sifatida yuborilmaydi - u tanlangan
      ovoz (voice) orqali avtomatik aniqlanadi.

Kerakli .env sozlamalari (app/core/config.py da allaqachon mavjud):
    YANDEX_API_KEY   - Yandex Cloud API kaliti (Api-Key ...)
    YANDEX_FOLDER_ID - Yandex Cloud folder ID
        (folder’ga ai.speechkit-stt.user VA ai.speechkit-tts.user
        rollari berilgan bo'lishi kerak)

Qo'shimcha ixtiyoriy sozlamalar (config.py ga qo'shildi):
    YANDEX_STT_LANG  - tanib olish tili (default: "uz-UZ")
    YANDEX_TTS_LANG  - hujjatlashtirish uchun saqlangan, v3 API'da ishlatilmaydi
    YANDEX_TTS_VOICE - ovoz (default: "nigora", o'zbek tili uchun rasmiy ovoz)

Eslatma: Yandex SpeechKit STT "short audio" recognize endpointi <= 1 daqiqa va
<= 1MB hajmdagi audio uchun mos keladi (Telegram ovozli xabarlar odatda
shu chegaraga to'g'ri keladi va OggOpus formatida keladi, shuning uchun
formatni o'zgartirmasdan to'g'ridan-to'g'ri yuborsa bo'ladi).

Kerakli qo'shimcha kutubxonalar (requirements.txt ga qo'shildi):
    yandexcloud  - Yandex Cloud'ning rasmiy Python SDK'si. Bizga undan faqat
                   TTS v3 uchun tayyor generatsiya qilingan protobuf/gRPC
                   modullari (yandex.cloud.ai.tts.v3.*) kerak.
    grpcio       - yandexcloud paketining o'zi ham buni talab qiladi,
                   lekin aniqlik uchun alohida yozib qo'yildi.
"""

import logging

import grpc
import httpx

from app.core.config import settings
from yandex.cloud.ai.tts.v3 import tts_pb2, tts_service_pb2_grpc

logger = logging.getLogger(__name__)

STT_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
TTS_V3_ENDPOINT = "tts.api.cloud.yandex.net:443"


class YandexSpeechError(Exception):
    """Yandex SpeechKit bilan bog'liq xatoliklar uchun umumiy exception."""


def _auth_header() -> dict:
    if not settings.YANDEX_API_KEY:
        raise YandexSpeechError(
            "YANDEX_API_KEY sozlanmagan. .env faylga YANDEX_API_KEY va "
            "YANDEX_FOLDER_ID qiymatlarini qo'shing."
        )
    return {"Authorization": f"Api-Key {settings.YANDEX_API_KEY}"}


def _grpc_metadata() -> tuple:
    if not settings.YANDEX_API_KEY or not settings.YANDEX_FOLDER_ID:
        raise YandexSpeechError(
            "YANDEX_API_KEY va/yoki YANDEX_FOLDER_ID sozlanmagan. .env faylni "
            "tekshiring."
        )
    return (
        ("authorization", f"Api-Key {settings.YANDEX_API_KEY}"),
        ("x-folder-id", settings.YANDEX_FOLDER_ID),
    )


async def speech_to_text(
    audio_bytes: bytes,
    audio_format: str = "oggopus",
    lang: str | None = None,
    sample_rate_hertz: int | None = None,
) -> str:
    """
    Audio baytlarni (ogg/opus, lpcm yoki mp3) matnga aylantiradi.
    Yandex SpeechKit STT API v1 orqali ishlaydi ("uz-UZ" shu yerda ishlaydi).

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


_CONTAINER_AUDIO_TYPES = {
    "oggopus": tts_pb2.ContainerAudio.OGG_OPUS,
    "mp3": tts_pb2.ContainerAudio.MP3,
    "lpcm": tts_pb2.ContainerAudio.WAV,  # eslatma: endi WAV header bilan keladi
}


async def text_to_speech(
    text: str,
    voice: str | None = None,
    lang: str | None = None,
    audio_format: str = "oggopus",
    speed: float = 1.0,
) -> bytes:
    """
    Matnni ovozli audio (bytes) ga aylantiradi. Yandex SpeechKit TTS API v3
    (gRPC) orqali ishlaydi, chunki eski v1 API "uz-UZ" tilini qo'llamaydi.

    `lang` parametri faqat moslik (backward-compat) uchun qoldirilgan - u
    hech qanday ta'sir qilmaydi, chunki API v3'da til tanlangan ovoz (voice)
    orqali aniqlanadi. O'zbekcha uchun voice="nigora" (default), ruscha uchun
    masalan voice="filipp" kabi qiymat berish mumkin.
    """
    if not text or not text.strip():
        raise YandexSpeechError("Ovozlashtirish uchun matn bo'sh bo'lmasligi kerak.")

    text = text[:4900]

    container_type = _CONTAINER_AUDIO_TYPES.get(audio_format)
    if container_type is None:
        raise YandexSpeechError(
            f"Noto'g'ri audio format: {audio_format}. Ruxsat etilganlar: "
            f"{sorted(_CONTAINER_AUDIO_TYPES)}"
        )

    request = tts_pb2.UtteranceSynthesisRequest(
        text=text,
        hints=[
            tts_pb2.Hints(voice=voice or settings.YANDEX_TTS_VOICE),
            tts_pb2.Hints(speed=speed),
        ],
        output_audio_spec=tts_pb2.AudioFormatOptions(
            container_audio=tts_pb2.ContainerAudio(container_audio_type=container_type)
        ),
    )

    try:
        metadata = _grpc_metadata()
    except YandexSpeechError:
        raise

    audio_chunks: list[bytes] = []
    try:
        async with grpc.aio.secure_channel(
            TTS_V3_ENDPOINT, grpc.ssl_channel_credentials()
        ) as channel:
            stub = tts_service_pb2_grpc.SynthesizerStub(channel)
            call = stub.UtteranceSynthesis(request, metadata=metadata, timeout=30.0)
            async for response in call:
                audio_chunks.append(response.audio_chunk.data)
    except grpc.aio.AioRpcError as exc:
        logger.error("Yandex TTS (v3) xatoligi: %s - %s", exc.code(), exc.details())
        raise YandexSpeechError(f"Yandex TTS xatoligi: {exc.details()}") from exc
    except Exception as exc:
        logger.exception("Yandex TTS (v3) so'roviga ulanishda xatolik")
        raise YandexSpeechError(f"Yandex TTS ga ulanib bo'lmadi: {exc}") from exc

    if not audio_chunks:
        raise YandexSpeechError("Yandex TTS bo'sh audio qaytardi.")

    return b"".join(audio_chunks)