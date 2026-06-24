from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

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
from app.ai.rag import generate_answer

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