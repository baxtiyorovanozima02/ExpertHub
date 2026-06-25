"""
app/api/chat.py

O'zgarishlar:
  4. STREAMING — /stream endpoint qo'shildi.
     Foydalanuvchi 3-5 soniya kutmaydi, javobni harfma-harf ko'radi.
     Server-Sent Events (SSE) formatida uzatiladi.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import json

from app.core.database import get_db
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.chat import (
    ConversationCreate,
    ConversationOut,
    MessageCreate,
    MessageOut,
    ChatHistoryOut,
)
from app.services.auth import get_current_user
from app.ai.rag import generate_answer, generate_answer_stream

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
    conversation = Conversation(user_id=current_user.id, category_id=payload.category_id)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.post("/{conversation_id}/message", response_model=MessageOut)
def send_message(
    conversation_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Oddiy (bloklovchi) endpoint — barcha javob tayyorlangach qaytaradi.
    Mavjud integratsiyalar uchun saqlab qolindi.
    """
    conversation = _get_owned_conversation(db, conversation_id, current_user)

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
    )

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer_text,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    return assistant_message


@router.post("/{conversation_id}/stream")
async def stream_message(
    conversation_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    STREAMING endpoint — Server-Sent Events (SSE) orqali token-by-token javob.

    Frontend ulash misoli (JavaScript):
        const es = new EventSource('/api/chat/1/stream', { ... });
        es.addEventListener('token', e => output += e.data);
        es.addEventListener('done',  e => { const msg = JSON.parse(e.data); ... });
        es.addEventListener('error', e => console.error(e.data));

    SSE format:
        event: token
        data: <matn bo'lagi>\n\n

        event: done
        data: {"id": 12, "content": "...", "role": "assistant"}\n\n
    """
    conversation = _get_owned_conversation(db, conversation_id, current_user)

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

            done_data = {
                "id": assistant_message.id,
                "conversation_id": assistant_message.conversation_id,
                "role": assistant_message.role,
                "content": assistant_message.content,
            }
            yield f"event: done\ndata: {json.dumps(done_data, ensure_ascii=False)}\n\n"

        except Exception as exc:
            error_msg = f"Xato yuz berdi: {str(exc)}"
            yield f"event: error\ndata: {json.dumps(error_msg)}\n\n"

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