# app/ai/rag.py
from typing import Optional, List, AsyncIterator
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

from app.core.config import settings
from app.ai.search import find_relevant_chunks
from app.ai.reranking import rerank_chunks
from app.models.message import Message


_COARSE_TOP_K = 8
_RERANK_TOP_K = 3

_HISTORY_LIMIT = 6


_SYSTEM_PROMPT = (
    "Sen ExpertHub platformasidagi ekspert yordamchi AI'san.\n\n"
    "QO'IDALAR:\n"
    "1. FAQAT quyida berilgan kontekstdan foydalanib javob ber.\n"
    "2. Agar kontekstda javob topilmasa — 'Berilgan hujjatlarda bu "
    "ma'lumot topilmadi.' deb yoz. Taxmin qilma, to'qima.\n"
    "3. Javobingda qaysi hujjat/manbadan olganingni qisqacha ayt "
    "(masalan: '[1-manba]', '[2-manba]').\n"
    "4. Javobni ro'yxat yoki qisqa paragraf shaklida ber — ixcham bo'lsin.\n"
    "5. O'zbek tilida so'zla.\n\n"
    "KONTEKST (manbalar):\n{context}"
)

_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PROMPT),
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


def _build_context(db: Session, question: str, category_id: Optional[int]) -> str:
    raw_chunks = find_relevant_chunks(
        db, question, category_id=category_id, top_k=_COARSE_TOP_K
    )
    if not raw_chunks:
        return "Tegishli ma'lumot topilmadi."

    best_chunks = rerank_chunks(question, raw_chunks, top_k=_RERANK_TOP_K)

    parts = []
    for i, chunk in enumerate(best_chunks, start=1):
        parts.append(f"[{i}-manba]\n{chunk.content}")
    return "\n\n".join(parts)


def _build_history(messages: List[Message]) -> list:
    """
    Oxirgi _HISTORY_LIMIT ta xabarni LangChain formatiga o'tkazadi.
    Juda ko'p xabar yuborilsa — token isrof bo'ladi, shuning uchun limit bor.
    """
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
    context = _build_context(db, question, category_id)
    chat_history = _build_history(history) if history else []
    chain = _PROMPT | _llm
    response = chain.invoke({
        "context": context,
        "question": question,
        "history": chat_history,
    })
    return response.content



async def generate_answer_stream(
    db: Session,
    question: str,
    category_id: Optional[int] = None,
    history: Optional[List[Message]] = None,
) -> AsyncIterator[str]:
    context = _build_context(db, question, category_id)
    chat_history = _build_history(history) if history else []
    chain = _PROMPT | _llm_streaming

    async for chunk in chain.astream({
        "context": context,
        "question": question,
        "history": chat_history,
    }):
        if hasattr(chunk, "content") and chunk.content:
            yield chunk.content


def generate_conversation_title(first_question: str) -> str:
    """
    Birinchi savoldan qisqa sarlavha yaratadi (History Page uchun).
    LLM ishlatmaydi — tez va arzon: dastlabki 60 belgini oladi.
    """
    title = first_question.strip().replace("\n", " ")
    if len(title) > 60:
        title = title[:57] + "..."
    return title