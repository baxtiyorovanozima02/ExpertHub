from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base


class DocumentFileType(str, enum.Enum):
    text = "text"
    document = "document"
    image = "image"
    audio = "audio"


class ExpertDocument(Base):
    __tablename__ = "expert_documents"

    id = Column(Integer, primary_key=True, index=True)
    expert_id = Column(Integer, ForeignKey("experts.id"), nullable=False)


    content = Column(String, nullable=True)

    source = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    file_type = Column(Enum(DocumentFileType), default=DocumentFileType.text, nullable=False)
    file_object_name = Column(String, nullable=True)
    original_filename = Column(String, nullable=True)

    expert = relationship("Expert", backref="documents")
