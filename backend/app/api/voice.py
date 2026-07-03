# app/api/voice.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io

from app.core.database import get_db
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.auth import get_current_user
from app.services.yandex_speech import speech_to_text, text_to_speech, YandexSpeechError
from app.ai.rag import generate_answer, generate_conversation_title

router = APIRouter(prefix="/api/voice", tags=["voice"])


def _get_owned_conversation(db: Session, conversation_id: int, user: User) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user.id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Suhbat topilmadi")
    return conversation


@router.post("/stt")
async def voice_to_text(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Ovozli faylni (ogg/opus, mp3, wav/lpcm) matnga aylantiradi.
    Frontend/mobil ilova mikrofon yozuvini shu endpointga yuboradi.
    """
    audio_bytes = await audio.read()

    audio_format = "oggopus"
    filename = (audio.filename or "").lower()
    if filename.endswith(".mp3"):
        audio_format = "mp3"
    elif filename.endswith(".wav"):
        audio_format = "lpcm"

    try:
        text = await speech_to_text(audio_bytes, audio_format=audio_format)
    except YandexSpeechError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {"text": text}


@router.post("/tts")
async def text_to_voice(
    text: str = Form(...),
    voice: str | None = Form(None),
    current_user: User = Depends(get_current_user),
):
    """
    Matnni ovozga aylantirib, OggOpus audio oqimi sifatida qaytaradi.
    """
    try:
        audio_bytes = await text_to_speech(text, voice=voice)
    except YandexSpeechError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type="audio/ogg",
        headers={"Content-Disposition": "attachment; filename=speech.ogg"},
    )


@router.post("/{conversation_id}/voice-message")
async def send_voice_message(
    conversation_id: int,
    audio: UploadFile = File(...),
    reply_with_audio: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    To'liq ovozli suhbat oqimi:
    ovoz -> matn (STT) -> RAG javob -> ovoz (TTS, ixtiyoriy).

    Javob sifatida foydalanuvchi va assistent xabarlari matni, shuningdek
    (agar reply_with_audio=True bo'lsa) assistent javobining ovozi
    base64 ko'rinishida qaytariladi.
    """
    conversation = _get_owned_conversation(db, conversation_id, current_user)

    audio_bytes = await audio.read()
    filename = (audio.filename or "").lower()
    audio_format = "mp3" if filename.endswith(".mp3") else (
        "lpcm" if filename.endswith(".wav") else "oggopus"
    )

    try:
        question_text = await speech_to_text(audio_bytes, audio_format=audio_format)
    except YandexSpeechError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if not question_text.strip():
        raise HTTPException(status_code=422, detail="Ovozdan matn aniqlanmadi, qaytadan urinib ko'ring.")

    history = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
        .all()
    )

    if not history and not conversation.title:
        conversation.title = generate_conversation_title(question_text)

    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=question_text,
    )
    db.add(user_message)
    db.commit()

    answer_text = generate_answer(
        db,
        question=question_text,
        category_id=conversation.category_id,
        history=history,
    )

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer_text,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    from sqlalchemy.sql import func
    conversation.updated_at = func.now()
    db.commit()

    result = {
        "question_text": question_text,
        "message": {
            "id": assistant_message.id,
            "conversation_id": assistant_message.conversation_id,
            "role": assistant_message.role,
            "content": assistant_message.content,
        },
    }

    if reply_with_audio:
        try:
            answer_audio = await text_to_speech(answer_text)
            import base64
            result["answer_audio_base64"] = base64.b64encode(answer_audio).decode("ascii")
            result["answer_audio_format"] = "oggopus"
        except YandexSpeechError as exc:
            # Matnli javob baribir qaytadi, faqat ovoz qo'shilmaydi.
            result["answer_audio_error"] = str(exc)

    return result