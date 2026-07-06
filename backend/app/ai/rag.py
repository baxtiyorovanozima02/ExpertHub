"""
RAG pipeline — Query Preprocessing, Chunk Source Tracking,
Multi-language, Reranking, Conversation History, Streaming.

  #4 Query preprocessing        — qisqa/noaniq savollar boyitiladi
  #5 Chunk source tracking      — javobda hujjat nomi ko'rsatiladi
  #8 Multi-language             — til aniqlanib, shu tilda javob beriladi
  #6 Conversation summarization — 20+ xabarda eski xabarlar xulosaga aylantiriladi
  #9 Fallback LLM               — OpenAI ishlamasa Claude/Gemini ga o'tadi
"""

from typing import Optional, List, AsyncIterator
from sqlalchemy.orm import Session
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.ai.llm_router import invoke_with_fallback, astream_with_fallback
from app.ai.search import find_relevant_chunks
from app.ai.reranking import rerank_chunks
from app.ai.query_preprocessor import expand_query, detect_language
from app.models.message import Message
from app.models.document_chunk import DocumentChunk
from app.models.expert_document import ExpertDocument


_COARSE_TOP_K        = 8
_RERANK_TOP_K        = 3
_SUMMARIZE_THRESHOLD = 20
_RECENT_KEEP         = 6


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

_SUMMARY_PROMPTS = {
    "uz": (
        "Quyidagi suhbat tarixini QISQA va IXCHAM xulosa qil (3-5 gap). "
        "Faqat muhim faktlarni, kontekstni va foydalanuvchi haqidagi ma'lumotlarni saqla. "
        "Xulosa o'zbek tilida bo'lsin.\n\nSUHBAT:\n{history}"
    ),
    "ru": (
        "Сделай КРАТКОЕ и СЖАТОЕ резюме следующей истории разговора (3-5 предложений). "
        "Сохрани только важные факты, контекст и информацию о пользователе. "
        "Резюме должно быть на русском языке.\n\nИСТОРИЯ:\n{history}"
    ),
    "en": (
        "Summarize the following conversation history BRIEFLY and CONCISELY (3-5 sentences). "
        "Keep only important facts, context, and user information. "
        "The summary must be in English.\n\nHISTORY:\n{history}"
    ),
}


def _get_prompt(lang: str) -> ChatPromptTemplate:
    system = _SYSTEM_PROMPTS.get(lang, _SYSTEM_PROMPTS["uz"])
    return ChatPromptTemplate.from_messages([
        ("system", system),
        ("placeholder", "{history}"),
        ("human", "{question}"),
    ])


def _get_source_name(chunk: DocumentChunk, db: Session) -> str:
    try:
        doc = db.query(ExpertDocument).filter(
            ExpertDocument.id == chunk.document_id
        ).first()
        if doc:
            return doc.original_filename or doc.source or f"Hujjat #{doc.id}"
    except Exception:
        pass
    return "Noma'lum manba"


_NOT_FOUND_MESSAGES = {
    "uz": "Berilgan hujjatlarda bu ma'lumot topilmadi.",
    "ru": "В предоставленных документах эта информация не найдена.",
    "en": "This information was not found in the provided documents.",
}


def _build_context(db: Session, question: str, category_id: Optional[int]) -> tuple[str, bool]:
    """
    Returns (context_text, found).

    MUHIM TUZATISH: avval hech qanday tegishli chunk topilmasa ham,
    "Tegishli ma'lumot topilmadi." matni LLM'ga kontekst sifatida
    yuborilib, LLM baribir chaqirilardi. LLM esa promptdagi "faqat
    kontekstdan foydalan" ko'rsatmasiga har doim ham qat'iy amal
    qilavermaydi va o'zining umumiy bilimidan (hujjatlarga aloqasi
    yo'q) javob to'qib chiqarishi mumkin edi — foydalanuvchi aynan
    shuni ko'rgan ("umumiy javob qaytaradi"). Endi `found=False`
    bo'lganda chaqiruvchi (generate_answer/_stream) LLM'ni umuman
    chaqirmasdan, standart "topilmadi" xabarini qaytaradi — bu orqali
    javob HAR DOIM faqat yuklangan hujjatlarga asoslanishi kafolatlanadi.
    """
    raw_chunks = find_relevant_chunks(
        db, question, category_id=category_id, top_k=_COARSE_TOP_K
    )
    if not raw_chunks:
        return "Tegishli ma'lumot topilmadi.", False

    best_chunks = rerank_chunks(question, raw_chunks, top_k=_RERANK_TOP_K)

    parts = []
    for chunk in best_chunks:
        source_name = _get_source_name(chunk, db)
        parts.append(f"[{source_name}]\n{chunk.content}")

    return "\n\n".join(parts), True


def _summarize_messages(messages: List[Message], lang: str) -> str:
    history_text = "\n".join(
        f"{'Foydalanuvchi' if m.role == 'user' else 'Assistent'}: {m.content}"
        for m in messages
    )
    prompt_text = _SUMMARY_PROMPTS.get(lang, _SUMMARY_PROMPTS["uz"]).format(
        history=history_text
    )
    summary_prompt = ChatPromptTemplate.from_messages([("human", "{text}")])
    response = invoke_with_fallback(summary_prompt, {"text": prompt_text})
    return response.content.strip()


def _build_history(messages: List[Message], lang: str = "uz") -> list:
    if len(messages) <= _SUMMARIZE_THRESHOLD:
        history = []
        for m in messages:
            if m.role == "user":
                history.append(HumanMessage(content=m.content))
            else:
                history.append(AIMessage(content=m.content))
        return history

    old_messages    = messages[:-_RECENT_KEEP]
    recent_messages = messages[-_RECENT_KEEP:]

    summary = _summarize_messages(old_messages, lang)

    history = [
        SystemMessage(content=f"[Oldingi suhbat xulosasi]\n{summary}")
    ]
    for m in recent_messages:
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
    expanded_q   = expand_query(question, history)
    lang         = detect_language(question)
    context, found = _build_context(db, expanded_q, category_id)

    if not found:
        # Hujjatlarda tegishli ma'lumot topilmasa, LLM umuman
        # chaqirilmaydi — shu orqali "hujjatlarga aloqasi yo'q umumiy
        # javob" berilishining oldi butunlay olinadi.
        return _NOT_FOUND_MESSAGES.get(lang, _NOT_FOUND_MESSAGES["uz"])

    chat_history = _build_history(history, lang) if history else []
    prompt       = _get_prompt(lang)

    response = invoke_with_fallback(prompt, {
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
    context, found = _build_context(db, expanded_q, category_id)

    if not found:
        yield _NOT_FOUND_MESSAGES.get(lang, _NOT_FOUND_MESSAGES["uz"])
        return

    chat_history = _build_history(history, lang) if history else []
    prompt       = _get_prompt(lang)

    async for token in astream_with_fallback(prompt, {
        "context":  context,
        "question": question,
        "history":  chat_history,
    }):
        yield token


def generate_conversation_title(first_question: str) -> str:
    title = first_question.strip().replace("\n", " ")
    if len(title) > 60:
        title = title[:57] + "..."
    return title