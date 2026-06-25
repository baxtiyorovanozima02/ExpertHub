# app/schemas/chat.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ConversationCreate(BaseModel):
    category_id: Optional[int] = None
    title: Optional[str] = None


class ConversationOut(BaseModel):
    id: int
    user_id: int
    category_id: Optional[int] = None
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationListOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ConversationOut]


class ConversationTitleUpdate(BaseModel):
    title: str


class MessageCreate(BaseModel):
    content: str


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatHistoryOut(BaseModel):
    conversation: ConversationOut
    messages: List[MessageOut]