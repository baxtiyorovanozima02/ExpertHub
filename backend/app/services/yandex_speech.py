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
import io
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


STT_CHUNK_SECONDS = 50
STT_MAX_CHUNK_BYTES = 900 * 1024


class YandexSpeechError(Exception):
    """Yandex SpeechKit bilan bog'liq xatoliklar uchun umumiy exception."""


_MAX_ERROR_MESSAGE_CHARS = 300


def _short_error_message(exc: Exception) -> str:
    message = str(exc)
    if len(message) > _MAX_ERROR_MESSAGE_CHARS:
        message = message[:_MAX_ERROR_MESSAGE_CHARS].rstrip() + "... (to'liq xato server logida)"
    return message


def _sniff_audio_format(audio_bytes: bytes) -> str | None:
    head = audio_bytes[:16]
    if head.startswith(b"OggS"):
        return "ogg"
    if head.startswith(b"RIFF"):
        return "wav"
    if head[4:8] == b"ftyp":
        return "mp4"
    if head.startswith(b"ID3") or (len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
        return "mp3"
    return None


def _load_audio_segment(audio_bytes: bytes, expected_pydub_format: str) -> AudioSegment:
    try:
        return AudioSegment.from_file(io.BytesIO(audio_bytes), format=expected_pydub_format)
    except Exception as first_exc:
        logger.warning(
            "Audio '%s' formatida ochilmadi, muqobil formatlarni sinab ko'ramiz: %s",
            expected_pydub_format, _short_error_message(first_exc),
        )
        sniffed = _sniff_audio_format(audio_bytes)
        if sniffed and sniffed != expected_pydub_format:
            try:
                return AudioSegment.from_file(io.BytesIO(audio_bytes), format=sniffed)
            except Exception:
                pass
        try:
            return AudioSegment.from_file(io.BytesIO(audio_bytes))
        except Exception:
            raise first_exc


def _export_oggopus(segment: AudioSegment) -> bytes:
    """AudioSegment'ni Yandex STT har doim qabul qiladigan OggOpus formatiga eksport qiladi."""
    out = io.BytesIO()
    segment.export(out, format="ogg", codec="libopus")
    return out.getvalue()


def _normalize_audio_for_stt(audio_bytes: bytes, guessed_format: str) -> bytes:
    """
    Yandex STT v1 recognize endpointi ba'zi formatlarni (masalan mp3) doim
    ham qabul qilavermaydi ("Invalid audio format: mp3" xatoligi shundan
    kelib chiqadi). Shuning uchun, agar audio allaqachon haqiqiy OggOpus
    bo'lmasa, uni ffmpeg/pydub orqali OggOpus'ga aylantiramiz va shu holda
    Yandex'ga yuboramiz. Bu deyarli barcha manba formatlarini (mp3, wav,
    webm, m4a/aac) qamrab oladi, chunki ffmpeg ularning barchasini decode
    qila oladi, OggOpus esa Yandex tomonidan har doim qo'llab-quvvatlanadi.
    """
    if guessed_format == "oggopus" and _sniff_audio_format(audio_bytes) in (None, "ogg"):
        return audio_bytes

    pydub_format = _PYDUB_FORMAT_NAMES.get(guessed_format, guessed_format)
    segment = _load_audio_segment(audio_bytes, pydub_format)
    return _export_oggopus(segment)


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


def _split_audio_into_chunks(
    audio_bytes: bytes,
    pydub_format: str,
    chunk_seconds: int = STT_CHUNK_SECONDS,
    max_chunk_bytes: int = STT_MAX_CHUNK_BYTES,
) -> list[bytes]:
    """
    Uzun/katta audio faylni Yandex "short audio" endpointi qabul qiladigan
    xavfsiz o'lchamdagi (<=1 daqiqa va <=1MB) bo'laklarga bo'ladi.

    Avval vaqt bo'yicha (chunk_seconds) bo'linadi. Agar shunda ham bo'lak
    hajmi max_chunk_bytes'dan katta chiqib qolsa (masalan siqilmagan wav
    yoki yuqori bitreyt formatlar uchun), bo'lak yana ikkiga bo'linadi -
    bu jarayon rekursiv ravishda hajm yetarlicha kichik bo'lguncha davom
    etadi.
    """
    audio = _load_audio_segment(audio_bytes, pydub_format)
    total_ms = len(audio)
    chunk_ms = chunk_seconds * 1000

    raw_pieces: list[AudioSegment] = []
    start = 0
    if total_ms == 0:
        raw_pieces = [audio]
    else:
        while start < total_ms:
            raw_pieces.append(audio[start:start + chunk_ms])
            start += chunk_ms

    def _export(segment: AudioSegment) -> bytes:
        out = io.BytesIO()
        segment.export(out, format=pydub_format)
        return out.getvalue()

    final_chunks: list[bytes] = []

    def _process(segment: AudioSegment):
        data = _export(segment)
        if len(data) <= max_chunk_bytes or len(segment) <= 2000:

            final_chunks.append(data)
            return
        half = len(segment) // 2
        _process(segment[:half])
        _process(segment[half:])

    for piece in raw_pieces:
        _process(piece)

    return final_chunks


async def speech_to_text_long(
    audio_bytes: bytes,
    audio_format: str = "oggopus",
    lang: str | None = None,
    sample_rate_hertz: int | None = None,
) -> str:
    """
    Istalgan uzunlik/hajmdagi audio faylni matnga aylantiradi.

    Yandex SpeechKit'ning "short audio" recognize endpointi <=1 daqiqa va
    <=1MB hajmdagi audio uchun mo'ljallangan bo'lib, bundan katta fayllarni
    to'g'ridan-to'g'ri yuborish xatolikka olib keladi. Shuning uchun bu
    funksiya:

      1. Audio shu chegaradan (vaqt va hajm bo'yicha) kichik bo'lsa -
         to'g'ridan-to'g'ri speech_to_text() ni chaqiradi (tezroq yo'l).
      2. Aks holda audio ffmpeg/pydub yordamida xavfsiz kichik bo'laklarga
         bo'linadi, har bir bo'lak navbat bilan Yandex STT'ga yuboriladi
         va natijada olingan matnlar birlashtiriladi.

    Shu tarzda foydalanuvchi tomonidan yuborilgan audio uzunligi yoki
    hajmiga hech qanday sun'iy chegara qo'yilmaydi.
    """
    if not audio_bytes:
        raise YandexSpeechError("Audio ma'lumot bo'sh.")


    try:
        audio_bytes = await asyncio.to_thread(
            _normalize_audio_for_stt, audio_bytes, audio_format
        )
    except Exception as exc:
        logger.exception("Audioni OggOpus'ga normallashtirishda xatolik")
        raise YandexSpeechError(
            f"Audio faylni qayta ishlab bo'lmadi (format noto'g'ri yoki fayl buzilgan): "
            f"{_short_error_message(exc)}"
        ) from exc
    audio_format = "oggopus"

    is_small_enough = len(audio_bytes) <= STT_MAX_CHUNK_BYTES

    pydub_format = _PYDUB_FORMAT_NAMES.get(audio_format, "ogg")

    if is_small_enough:
        try:
            duration_ms = len(
                await asyncio.to_thread(_load_audio_segment, audio_bytes, pydub_format)
            )
        except Exception:
            duration_ms = None

        if duration_ms is None or duration_ms <= STT_CHUNK_SECONDS * 1000:
            return await speech_to_text(
                audio_bytes,
                audio_format=audio_format,
                lang=lang,
                sample_rate_hertz=sample_rate_hertz,
            )

    try:
        chunks = await asyncio.to_thread(
            _split_audio_into_chunks, audio_bytes, pydub_format
        )
    except Exception as exc:
        logger.exception("Audio bo'laklarga bo'lishda xatolik")
        raise YandexSpeechError(
            f"Audio faylni qayta ishlab bo'lmadi (format noto'g'ri yoki fayl buzilgan): "
            f"{_short_error_message(exc)}"
        ) from exc

    if not chunks:
        raise YandexSpeechError("Audio bo'sh yoki noto'g'ri formatda.")

    logger.info(
        "Uzun audio %d bo'lakka bo'lindi (STT_CHUNK_SECONDS=%d)",
        len(chunks), STT_CHUNK_SECONDS,
    )

    recognized_parts: list[str] = []
    for index, chunk_bytes in enumerate(chunks, start=1):
        try:
            part_text = await speech_to_text(
                chunk_bytes,
                audio_format=audio_format,
                lang=lang,
                sample_rate_hertz=sample_rate_hertz,
            )
        except YandexSpeechError:
            logger.error("STT bo'lagi %d/%d tanib olishda xatolik", index, len(chunks))
            raise
        if part_text and part_text.strip():
            recognized_parts.append(part_text.strip())

    return " ".join(recognized_parts).strip()


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