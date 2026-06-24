from typing import Optional, List
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

from app.core.config import settings
from app.ai.search import find_relevant_chunks
from app.models.message import Message

_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Sen ExpertHub platformasidagi yordamchi AI'san. Faqat quyida berilgan "
        "ekspert ma'lumotlariga (kontekst) asoslanib javob ber. Agar kontekstda "
        "javob topilmasa, buni ochiq aytib o't, taxmin qilma.\n\n"
        "Kontekst:\n{context}",
    ),
    ("human", "{question}"),
])

_llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=settings.OPENAI_API_KEY,
    temperature=0.3,
)


def _build_context(db: Session, question: str, category_id: Optional[int]) -> str:
    chunks = find_relevant_chunks(db, question, category_id=category_id, top_k=5)
    if not chunks:
        return "Tegishli ma'lumot topilmadi."
    return "\n\n".join(f"- {chunk.content}" for chunk in chunks)


def generate_answer(db: Session, question: str, category_id: Optional[int] = None) -> str:
    """
    RAG pipeline: savolga mos kontekstni (eng yaqin chunklarni) topadi,
    LLM'ga yuboradi va javobni qaytaradi.
    """
    context = _build_context(db, question, category_id)
    chain = _PROMPT | _llm
    response = chain.invoke({"context": context, "question": question})
    return response.content


def build_chat_history(messages: List[Message]):
    """Eski xabarlarni LangChain message obyektlariga aylantiradi (kerak bo'lsa)."""
    history = []
    for m in messages:
        if m.role == "user":
            history.append(HumanMessage(content=m.content))
        else:
            history.append(AIMessage(content=m.content))
    return history