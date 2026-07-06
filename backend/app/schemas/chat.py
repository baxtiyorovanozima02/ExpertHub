from pydantic import BaseModel, field_validator
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
    feedback: Optional[int] = None
    created_at: datetime


    answer_audio_base64: Optional[str] = None
    answer_audio_format: Optional[str] = None
    answer_audio_error: Optional[str] = None

    class Config:
        from_attributes = True


class ChatHistoryOut(BaseModel):
    conversation: ConversationOut
    messages: List[MessageOut]


class MessageFeedback(BaseModel):
    """Feedback: 1 = thumbs up, -1 = thumbs down"""
    value: int

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: int) -> int:
        if v not in (1, -1):
            raise ValueError("Feedback qiymati faqat 1 (👍) yoki -1 (👎) bo'lishi mumkin")
        return v