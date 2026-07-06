from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
import base64
import json

from app.core.database import get_db
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.chat import (
    ConversationCreate,
    ConversationOut,
    ConversationListOut,
    MessageCreate,
    MessageOut,
    ChatHistoryOut,
    ConversationTitleUpdate,
)
from app.services.auth import get_current_user
from app.ai.rag import generate_answer, generate_answer_stream, generate_conversation_title
from app.ai.query_preprocessor import detect_language
from app.services.yandex_speech import text_to_speech, get_voice_for_lang, YandexSpeechError

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _get_owned_conversation(db: Session, conversation_id: int, user: User) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user.id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Suhbat topilmadi")
    return conversation



@router.post("/", response_model=ConversationOut)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = Conversation(
        user_id=current_user.id,
        category_id=payload.category_id,
        title=payload.title,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/", response_model=ConversationListOut)
def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Foydalanuvchining barcha suhbatlari — oxirgisi birinchi.
    History Page uchun ishlatiladi.
    """
    query = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return ConversationListOut(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/search", response_model=ConversationListOut)
def search_conversations(
    q: str = Query(..., min_length=1, description="Qidiruv so'zi"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Suhbat sarlavhalari va xabarlar ichidan qidiradi.
    History Page dagi search box uchun.
    """
    pattern = f"%{q}%"

    matched_ids = (
        db.query(Message.conversation_id)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(
            Conversation.user_id == current_user.id,
            Message.content.ilike(pattern),
        )
        .distinct()
        .subquery()
    )

    query = (
        db.query(Conversation)
        .filter(
            Conversation.user_id == current_user.id,
            or_(
                Conversation.title.ilike(pattern),
                Conversation.id.in_(matched_ids),
            ),
        )
        .order_by(Conversation.updated_at.desc())
    )

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return ConversationListOut(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )



@router.patch("/{conversation_id}/title", response_model=ConversationOut)
def update_title(
    conversation_id: int,
    payload: ConversationTitleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = _get_owned_conversation(db, conversation_id, current_user)
    conversation.title = payload.title
    db.commit()
    db.refresh(conversation)
    return conversation



@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = _get_owned_conversation(db, conversation_id, current_user)
    db.delete(conversation)
    db.commit()
    return {"detail": "Suhbat o'chirildi"}



@router.post("/{conversation_id}/message", response_model=MessageOut)
async def send_message(
    conversation_id: int,
    payload: MessageCreate,
    reply_with_audio: bool = Query(
        False,
        description="true bo'lsa, matn javobi bilan birga ovozli (base64) javob ham qaytariladi.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = _get_owned_conversation(db, conversation_id, current_user)

    history = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
        .all()
    )

    if not history and not conversation.title:
        conversation.title = generate_conversation_title(payload.content)

    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=payload.content,
    )
    db.add(user_message)
    db.commit()

    answer_text = generate_answer(
        db,
        question=payload.content,
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

    result = MessageOut.model_validate(assistant_message)


    if reply_with_audio:
        try:
            answer_lang = detect_language(answer_text)
            answer_voice = get_voice_for_lang(answer_lang)
            answer_audio_bytes = await text_to_speech(answer_text, voice=answer_voice)
            result.answer_audio_base64 = base64.b64encode(answer_audio_bytes).decode("ascii")
            result.answer_audio_format = "oggopus"
        except YandexSpeechError as exc:
            result.answer_audio_error = str(exc)

    return result



@router.post("/{conversation_id}/stream")
async def stream_message(
    conversation_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = _get_owned_conversation(db, conversation_id, current_user)

    history = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
        .all()
    )

    if not history and not conversation.title:
        conversation.title = generate_conversation_title(payload.content)
        db.commit()

    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=payload.content,
    )
    db.add(user_message)
    db.commit()

    async def event_generator():
        full_response = []
        try:
            async for token in generate_answer_stream(
                db,
                question=payload.content,
                category_id=conversation.category_id,
                history=history,
            ):
                full_response.append(token)
                yield f"event: token\ndata: {json.dumps(token)}\n\n"

            answer_text = "".join(full_response)
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

            done_data = {
                "id": assistant_message.id,
                "conversation_id": assistant_message.conversation_id,
                "role": assistant_message.role,
                "content": assistant_message.content,
            }
            yield f"event: done\ndata: {json.dumps(done_data, ensure_ascii=False)}\n\n"

        except Exception as exc:
            yield f"event: error\ndata: {json.dumps(str(exc))}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )




@router.get("/{conversation_id}/history", response_model=ChatHistoryOut)
def get_history(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = _get_owned_conversation(db, conversation_id, current_user)
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
        .all()
    )
    return ChatHistoryOut(conversation=conversation, messages=messages)



from app.schemas.chat import MessageFeedback  # noqa: E402 (append import)


@router.post("/{conversation_id}/messages/{message_id}/feedback", response_model=MessageOut)
def set_message_feedback(
    conversation_id: int,
    message_id: int,
    payload: MessageFeedback,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    #7 Feedback sistema: foydalanuvchi 👍 (1) yoki 👎 (-1) bosadi.
    Faqat o'z suhbatiga tegishli assistant xabarlarga feedback berish mumkin.
    """
    conversation = _get_owned_conversation(db, conversation_id, current_user)

    message = (
        db.query(Message)
        .filter(
            Message.id == message_id,
            Message.conversation_id == conversation.id,
        )
        .first()
    )
    if not message:
        raise HTTPException(status_code=404, detail="Xabar topilmadi")

    if message.role != "assistant":
        raise HTTPException(
            status_code=400,
            detail="Feedback faqat assistant xabarlariga berilishi mumkin",
        )

    message.feedback = payload.value
    db.commit()
    db.refresh(message)
    return message


@router.delete("/{conversation_id}/messages/{message_id}/feedback", response_model=MessageOut)
def remove_message_feedback(
    conversation_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Feedbackni olib tashlash (NULL ga qaytarish)."""
    conversation = _get_owned_conversation(db, conversation_id, current_user)

    message = (
        db.query(Message)
        .filter(
            Message.id == message_id,
            Message.conversation_id == conversation.id,
        )
        .first()
    )
    if not message:
        raise HTTPException(status_code=404, detail="Xabar topilmadi")

    message.feedback = None
    db.commit()
    db.refresh(message)
    return message