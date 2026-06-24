from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class DocumentChunk(Base):
    """
    Bitta ExpertDocument bir nechta DocumentChunk'ga bo'linadi.
    Matn shu yerda (Postgres'da) saqlanadi. Har bir chunk uchun
    embedding esa Qdrant'da (chunk.id bo'yicha) saqlanadi - shuning
    uchun bu yerda alohida embedding relationship kerak emas.
    """

    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("expert_documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("ExpertDocument", backref="chunks")