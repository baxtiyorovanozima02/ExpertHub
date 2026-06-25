"""
app/ai/rag.py

RAG pipeline — Reranking va yaxshilangan Prompt bilan.

O'zgarishlar:
  2. RERANKING  — Qdrant 8 chunk topadi, CrossEncoder 3 tasini tanlaydi.
  3. PROMPT     — LLM taxmin qilmasin, ro'yxat ko'rinishida javob bersin,
                  manba (hujjat nomi yoki fragment) aytsin.
"""

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
    """
    1. Qdrant dan _COARSE_TOP_K ta chunk oladi.
    2. CrossEncoder bilan rerank qilib _RERANK_TOP_K tasini qoldiradi.
    3. Raqamlangan manba ko'rinishida qaytaradi.
    """
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



def generate_answer(
    db: Session,
    question: str,
    category_id: Optional[int] = None,
) -> str:
    """
    RAG pipeline: savol -> kontekst (rerank bilan) -> LLM -> javob.
    """
    context = _build_context(db, question, category_id)
    chain = _PROMPT | _llm
    response = chain.invoke({"context": context, "question": question})
    return response.content


async def generate_answer_stream(
    db: Session,
    question: str,
    category_id: Optional[int] = None,
) -> AsyncIterator[str]:
    """
    Streaming RAG: har bir token kelishi bilan yield qiladi.
    Frontend 3-5 soniya kutmaydi — harfma-harf ko'radi.
    """
    context = _build_context(db, question, category_id)
    chain = _PROMPT | _llm_streaming

    async for chunk in chain.astream({"context": context, "question": question}):
        if hasattr(chunk, "content") and chunk.content:
            yield chunk.content


def build_chat_history(messages: List[Message]):
    """Eski xabarlarni LangChain message obyektlariga aylantiradi."""
    history = []
    for m in messages:
        if m.role == "user":
            history.append(HumanMessage(content=m.content))
        else:
            history.append(AIMessage(content=m.content))
    return history