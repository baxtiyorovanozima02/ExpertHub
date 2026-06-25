# app/ai/rag.py
"""
RAG pipeline — Query Preprocessing, Chunk Source Tracking,
Multi-language, Reranking, Conversation History, Streaming.

Yangiliklar (1-tur):
  #4 Query preprocessing  — qisqa/noaniq savollar boyitiladi
  #5 Chunk source tracking — javobda hujjat nomi ko'rsatiladi
  #8 Multi-language        — til aniqlanib, shu tilda javob beriladi
"""

from typing import Optional, List, AsyncIterator
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

from app.core.config import settings
from app.ai.search import find_relevant_chunks
from app.ai.reranking import rerank_chunks
from app.ai.query_preprocessor import expand_query, detect_language
from app.models.message import Message
from app.models.document_chunk import DocumentChunk
from app.models.expert_document import ExpertDocument


_COARSE_TOP_K  = 8
_RERANK_TOP_K  = 3
_HISTORY_LIMIT = 6


_SYSTEM_PROMPTS = {
    "uz": (
        "Sen ExpertHub platformasidagi ekspert yordamchi AI'san.\n\n"
        "QO'IDALAR:\n"
        "1. FAQAT quyida berilgan kontekstdan foydalanib javob ber.\n"
        "2. Agar kontekstda javob topilmasa — 'Berilgan hujjatlarda bu "
        "ma'lumot topilmadi.' deb yoz. Taxmin qilma, to'qima.\n"
        "3. Har bir manba uchun hujjat nomini ko'rsat "
        "(masalan: '[Mehnat_shartnomasi.pdf]').\n"
        "4. Javobni ro'yxat yoki qisqa paragraf shaklida ber.\n"
        "5. O'ZBEK tilida javob ber.\n\n"
        "KONTEKST:\n{context}"
    ),
    "ru": (
        "Ты — экспертный ИИ-помощник платформы ExpertHub.\n\n"
        "ПРАВИЛА:\n"
        "1. Отвечай ТОЛЬКО на основе приведённого контекста.\n"
        "2. Если ответа нет — напиши 'В предоставленных документах "
        "эта информация не найдена.' Не придумывай.\n"
        "3. Указывай источник для каждого факта "
        "(например: '[Договор_труда.pdf]').\n"
        "4. Отвечай списком или кратким абзацем.\n"
        "5. Отвечай на РУССКОМ языке.\n\n"
        "КОНТЕКСТ:\n{context}"
    ),
    "en": (
        "You are an expert AI assistant on the ExpertHub platform.\n\n"
        "RULES:\n"
        "1. Answer ONLY based on the context provided below.\n"
        "2. If the answer is not in the context — say 'This information "
        "was not found in the provided documents.' Do not guess.\n"
        "3. Cite the document name for each fact "
        "(e.g. '[Employment_contract.pdf]').\n"
        "4. Answer in bullet points or a short paragraph.\n"
        "5. Answer in ENGLISH.\n\n"
        "CONTEXT:\n{context}"
    ),
}


def _get_prompt(lang: str) -> ChatPromptTemplate:
    system = _SYSTEM_PROMPTS.get(lang, _SYSTEM_PROMPTS["uz"])
    return ChatPromptTemplate.from_messages([
        ("system", system),
        ("placeholder", "{history}"),
        ("human", "{question}"),
    ])



_llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=settings.OPENAI_API_KEY,
    temperature=0.2,
)

_llm_streaming = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=settings.OPENAI_API_KEY,
    temperature=0.2,
    streaming=True,
)



def _get_source_name(chunk: DocumentChunk, db: Session) -> str:
    """
    Chunk ga tegishli hujjat nomini qaytaradi.
    original_filename bo'lmasa — source yoki 'Noma'lum manba'.
    """
    try:
        doc = db.query(ExpertDocument).filter(
            ExpertDocument.id == chunk.document_id
        ).first()
        if doc:
            return doc.original_filename or doc.source or f"Hujjat #{doc.id}"
    except Exception:
        pass
    return "Noma'lum manba"


def _build_context(db: Session, question: str, category_id: Optional[int]) -> str:
    """
    1. Qdrant dan raw chunklar oladi
    2. CrossEncoder bilan rerank qiladi
    3. Har bir chunk oldiga hujjat nomini qo'shadi  ← #5
    """
    raw_chunks = find_relevant_chunks(
        db, question, category_id=category_id, top_k=_COARSE_TOP_K
    )
    if not raw_chunks:
        return "Tegishli ma'lumot topilmadi."

    best_chunks = rerank_chunks(question, raw_chunks, top_k=_RERANK_TOP_K)

    parts = []
    for chunk in best_chunks:
        source_name = _get_source_name(chunk, db)
        parts.append(f"[{source_name}]\n{chunk.content}")

    return "\n\n".join(parts)


def _build_history(messages: List[Message]) -> list:
    recent = messages[-_HISTORY_LIMIT:] if len(messages) > _HISTORY_LIMIT else messages
    history = []
    for m in recent:
        if m.role == "user":
            history.append(HumanMessage(content=m.content))
        else:
            history.append(AIMessage(content=m.content))
    return history



def generate_answer(
    db: Session,
    question: str,
    category_id: Optional[int] = None,
    history: Optional[List[Message]] = None,
) -> str:
    expanded_q = expand_query(question, history)

    lang = detect_language(question)

    context      = _build_context(db, expanded_q, category_id)
    chat_history = _build_history(history) if history else []
    prompt       = _get_prompt(lang)
    chain        = prompt | _llm

    response = chain.invoke({
        "context":  context,
        "question": question,
        "history":  chat_history,
    })
    return response.content


async def generate_answer_stream(
    db: Session,
    question: str,
    category_id: Optional[int] = None,
    history: Optional[List[Message]] = None,
) -> AsyncIterator[str]:
    expanded_q   = expand_query(question, history)
    lang         = detect_language(question)
    context      = _build_context(db, expanded_q, category_id)
    chat_history = _build_history(history) if history else []
    prompt       = _get_prompt(lang)
    chain        = prompt | _llm_streaming

    async for chunk in chain.astream({
        "context":  context,
        "question": question,
        "history":  chat_history,
    }):
        if hasattr(chunk, "content") and chunk.content:
            yield chunk.content


def generate_conversation_title(first_question: str) -> str:
    title = first_question.strip().replace("\n", " ")
    if len(title) > 60:
        title = title[:57] + "..."
    return title