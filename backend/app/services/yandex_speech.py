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

    - UZUN MATNLAR (YANGI, chunking): Yandex TTS v3 bitta so'rovda juda
      uzun matnni qabul qilmaydi ("Too long text" xatoligi). Shuning uchun
      endi text_to_speech() uzun matnni jumlalar bo'yicha kichik bo'laklarga
      (har biri TTS_MAX_CHUNK_CHARS belgidan oshmaydigan) bo'lib, har bir
      bo'lakni alohida Yandex TTS orqali ovozga aylantiradi, so'ngra barcha
      audio bo'laklarni pydub/ffmpeg yordamida bitta yaxlit audio faylga
      birlashtiradi. Bo'laklar orasida www ovoz sifatini pasaytirmasligi
      uchun ffmpeg orqali qayta kodlash (re-encode) qilinadi, bu esa turli
      formatdagi (ogg/mp3/wav) bo'laklarni ham muammosiz birlashtirish
      imkonini beradi.

Kerakli .env sozlamalari (app/core/config.py da allaqachon mavjud):
    YANDEX_API_KEY   - Yandex Cloud API kaliti (Api-Key ...)
    YANDEX_FOLDER_ID - Yandex Cloud folder ID
        (folder'ga ai.speechkit-stt.user VA ai.speechkit-tts.user
        rollari berilgan bo'lishi kerak)

Qo'shimcha ixtiyoriy sozlamalar (config.py ga qo'shildi):
    YANDEX_STT_LANG  - tanib olish tili (default: "uz-UZ")
    YANDEX_TTS_LANG  - hujjatlashtirish uchun saqlangan, v3 API'da ishlatilmaydi
    YANDEX_TTS_VOICE - ovoz (default: "nigora", o'zbek tili uchun rasmiy ovoz)
    YANDEX_TTS_MAX_CHUNK_CHARS - bitta TTS so'roviga yuboriladigan matnning
        maksimal uzunligi (default: 350). Yandex TTS v3 uchun xavfsiz chegara.

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
    pydub        - (YANGI) audio bo'laklarni birlashtirish uchun. ffmpeg
                   binary talab qiladi - loyihaning Dockerfile'ida ffmpeg
                   allaqachon o'rnatilgan.
"""

import asyncio
import logging
import re

import grpc
import httpx
from pydub import AudioSegment

from app.core.config import settings
from yandex.cloud.ai.tts.v3 import tts_pb2, tts_service_pb2_grpc

logger = logging.getLogger(__name__)

STT_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
TTS_V3_ENDPOINT = "tts.api.cloud.yandex.net:443"


DEFAULT_TTS_MAX_CHUNK_CHARS = 350


class YandexSpeechError(Exception):
    """Yandex SpeechKit bilan bog'liq xatoliklar uchun umumiy exception."""


def get_voice_for_lang(lang: str | None) -> str:
    """
    Aniqlangan javob tiliga ('uz' | 'ru' | 'en') mos Yandex TTS ovozini
    qaytaradi.

    TUZATISH: avval barcha javoblar tildan qat'iy nazar
    settings.YANDEX_TTS_VOICE ("nigora", o'zbekcha ovoz) bilan
    o'qilardi. Endi RAG javobi qaysi tilda bo'lsa (app.ai.rag /
    query_preprocessor.detect_language natijasi), TTS ham shu tilga
    mos ovozdan foydalanadi. Noma'lum/bo'sh til kelsa — xavfsiz
    default sifatida o'zbekcha ovozga qaytiladi.
    """
    voice_by_lang = {
        "uz": settings.YANDEX_TTS_VOICE_UZ,
        "ru": settings.YANDEX_TTS_VOICE_RU,
        "en": settings.YANDEX_TTS_VOICE_EN,
    }
    return voice_by_lang.get((lang or "").lower(), settings.YANDEX_TTS_VOICE_UZ)


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
    "lpcm": tts_pb2.ContainerAudio.WAV,
}

_PYDUB_FORMAT_NAMES = {
    "oggopus": "ogg",
    "mp3": "mp3",
    "lpcm": "wav",
}


def _split_text_into_chunks(text: str, max_chars: int) -> list[str]:
    """
    Matnni jumlalar chegarasi bo'ylab, har biri max_chars belgidan
    oshmaydigan bo'laklarga ajratadi.

    Avval matn jumlalarga (. ! ? belgilaridan keyin) bo'linadi, so'ngra
    ketma-ket jumlalar max_chars ga sig'guncha bitta bo'lakka birlashtiriladi.
    Agar bitta jumlaning o'zi max_chars dan uzun bo'lsa (kamdan-kam holat),
    u so'zlar chegarasida majburan bo'lib tashlanadi.
    """
    text = text.strip()
    if not text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text)

    chunks: list[str] = []
    current = ""

    def _flush_current():
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(sentence) > max_chars:
            _flush_current()
            words = sentence.split(" ")
            piece = ""
            for word in words:
                candidate = f"{piece} {word}".strip()
                if len(candidate) > max_chars and piece:
                    chunks.append(piece.strip())
                    piece = word
                else:
                    piece = candidate
            if piece.strip():
                chunks.append(piece.strip())
            continue

        candidate = f"{current} {sentence}".strip()
        if len(candidate) > max_chars and current:
            _flush_current()
            current = sentence
        else:
            current = candidate

    _flush_current()
    return chunks


async def _synthesize_chunk(
    text: str,
    voice: str | None,
    audio_format: str,
    speed: float,
    container_type,
) -> bytes:
    """Bitta (qisqa) matn bo'lagini Yandex TTS v3 orqali ovozga aylantiradi."""

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

    metadata = _grpc_metadata()

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


def _concatenate_audio_chunks(audio_parts: list[bytes], pydub_format: str) -> bytes:
    """
    Bir nechta audio bo'lakni (bir xil formatdagi bytes) ffmpeg/pydub
    yordamida bitta yaxlit audio faylga birlashtiradi.

    Bu operatsiya CPU-bound (ffmpeg chaqiradi), shuning uchun uni chaqirgan
    joyda thread pool orqali ishlatish tavsiya etiladi (quyida
    text_to_speech ichida shunday qilingan).
    """
    if len(audio_parts) == 1:
        return audio_parts[0]

    combined: AudioSegment | None = None
    for part in audio_parts:
        segment = AudioSegment.from_file(
            __import__("io").BytesIO(part), format=pydub_format
        )
        combined = segment if combined is None else combined + segment

    out = __import__("io").BytesIO()
    combined.export(out, format=pydub_format)
    return out.getvalue()


async def text_to_speech(
    text: str,
    voice: str | None = None,
    lang: str | None = None,
    audio_format: str = "oggopus",
    speed: float = 1.0,
    max_chunk_chars: int | None = None,
) -> bytes:
    """
    Matnni ovozli audio (bytes) ga aylantiradi. Yandex SpeechKit TTS API v3
    (gRPC) orqali ishlaydi, chunki eski v1 API "uz-UZ" tilini qo'llamaydi.

    Agar matn uzun bo'lsa (Yandex TTS v3 bitta so'rovda qabul qila oladigan
    chegaradan katta bo'lsa), matn avtomatik ravishda jumlalar bo'yicha
    kichik bo'laklarga bo'linadi, har bir bo'lak alohida-alohida Yandex
    TTS'ga yuboriladi, so'ngra natijalar bitta yaxlit audio faylga
    birlashtiriladi. Bo'laklar ketma-ket (sequential) yuboriladi, chunki
    Yandex API bitta service account uchun parallel so'rovlar sonini
    cheklashi mumkin; agar tezlik muhim bo'lsa, buni keyinchalik
    asyncio.gather() bilan cheklangan concurrency'ga o'tkazish mumkin.

    `lang` parametri faqat moslik (backward-compat) uchun qoldirilgan - u
    hech qanday ta'sir qilmaydi, chunki API v3'da til tanlangan ovoz (voice)
    orqali aniqlanadi. O'zbekcha uchun voice="nigora" (default), ruscha uchun
    masalan voice="filipp" kabi qiymat berish mumkin.
    """
    if not text or not text.strip():
        raise YandexSpeechError("Ovozlashtirish uchun matn bo'sh bo'lmasligi kerak.")

    container_type = _CONTAINER_AUDIO_TYPES.get(audio_format)
    if container_type is None:
        raise YandexSpeechError(
            f"Noto'g'ri audio format: {audio_format}. Ruxsat etilganlar: "
            f"{sorted(_CONTAINER_AUDIO_TYPES)}"
        )

    chunk_limit = max_chunk_chars or settings.YANDEX_TTS_MAX_CHUNK_CHARS or DEFAULT_TTS_MAX_CHUNK_CHARS

    text_chunks = _split_text_into_chunks(text, chunk_limit)
    if not text_chunks:
        raise YandexSpeechError("Ovozlashtirish uchun matn bo'sh bo'lmasligi kerak.")

    logger.info(
        "TTS: matn %d belgidan iborat, %d ta bo'lakka bo'lindi (chunk_limit=%d)",
        len(text),
        len(text_chunks),
        chunk_limit,
    )

    audio_parts: list[bytes] = []
    for index, chunk in enumerate(text_chunks, start=1):
        try:
            part = await _synthesize_chunk(
                chunk, voice=voice, audio_format=audio_format, speed=speed,
                container_type=container_type,
            )
        except YandexSpeechError:
            logger.error("TTS bo'lagi %d/%d sintez qilishda xatolik", index, len(text_chunks))
            raise
        audio_parts.append(part)

    if len(audio_parts) == 1:
        return audio_parts[0]

    pydub_format = _PYDUB_FORMAT_NAMES.get(audio_format, "ogg")

    try:

        combined_audio = await asyncio.to_thread(
            _concatenate_audio_chunks, audio_parts, pydub_format
        )
    except Exception as exc:
        logger.exception("Audio bo'laklarni birlashtirishda xatolik")
        raise YandexSpeechError(f"Audio bo'laklarni birlashtirib bo'lmadi: {exc}") from exc

    return combined_audio