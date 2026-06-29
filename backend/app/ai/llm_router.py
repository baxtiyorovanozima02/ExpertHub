# app/ai/llm_router.py
"""
LLM Router — OpenAI / Claude / Gemini

Ishlash tartibi:
  1. PRIMARY_LLM da ko'rsatilgan model birinchi ishlatiladi
  2. U ishlamasa (API xatosi, limit, kalit yo'q) → keyingi ga o'tadi
  3. Hamma ishlamasa → xato qaytaradi

.env da sozlash:
  PRIMARY_LLM=openai
  OPENAI_API_KEY=sk-...
  ANTHROPIC_API_KEY=sk-ant-...
  GEMINI_API_KEY=AIza...
"""

import logging
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)


_FALLBACK_ORDER = {
    "openai":  ["openai",  "claude", "gemini"],
    "claude":  ["claude",  "openai", "gemini"],
    "gemini":  ["gemini",  "openai", "claude"],
}


def _make_openai_llm(streaming: bool = False):
    from app.core.config import settings
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY yo'q")
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.OPENAI_API_KEY,
        temperature=0.2,
        streaming=streaming,
    )


def _make_claude_llm(streaming: bool = False):
    from app.core.config import settings
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY yo'q")
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        raise RuntimeError("langchain-anthropic o'rnatilmagan: pip install langchain-anthropic")
    return ChatAnthropic(
        model="claude-haiku-4-5-20251001",  # tez va arzon model
        api_key=settings.ANTHROPIC_API_KEY,
        temperature=0.2,
        streaming=streaming,
    )


def _make_gemini_llm(streaming: bool = False):
    from app.core.config import settings
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY yo'q")
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError:
        raise RuntimeError("langchain-google-genai o'rnatilmagan: pip install langchain-google-genai")
    return ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.2,
        streaming=streaming,
    )


_LLM_FACTORIES = {
    "openai": _make_openai_llm,
    "claude": _make_claude_llm,
    "gemini": _make_gemini_llm,
}


def get_llm(streaming: bool = False):
    """
    Sozlamaga qarab LLM qaytaradi.
    Biri ishlamasa avtomatik keyingisiga o'tadi.

    Returns:
        LangChain chat model (OpenAI / Claude / Gemini)
    """
    from app.core.config import settings
    primary = settings.PRIMARY_LLM.lower()
    order = _FALLBACK_ORDER.get(primary, _FALLBACK_ORDER["openai"])

    last_error = None
    for name in order:
        factory = _LLM_FACTORIES.get(name)
        if not factory:
            continue
        try:
            llm = factory(streaming=streaming)
            if name != primary:
                logger.warning(f"LLM fallback: {primary} → {name}")
            else:
                logger.debug(f"LLM: {name} ishlatilmoqda")
            return llm
        except RuntimeError as e:
            logger.info(f"LLM '{name}' o'tkazib yuborildi: {e}")
            last_error = e
            continue

    raise RuntimeError(
        f"Hech qanday LLM ishlamadi. "
        f"Oxirgi xato: {last_error}. "
        f".env da kamida bitta API kalit bo'lishi kerak: "
        f"OPENAI_API_KEY, ANTHROPIC_API_KEY yoki GEMINI_API_KEY"
    )


def get_active_llm_name() -> str:
    """
    Hozir qaysi LLM ishlatilayotganini qaytaradi.
    Logging va monitoring uchun foydali.
    """
    from app.core.config import settings
    primary = settings.PRIMARY_LLM.lower()
    order = _FALLBACK_ORDER.get(primary, _FALLBACK_ORDER["openai"])

    for name in order:
        factory = _LLM_FACTORIES.get(name)
        if not factory:
            continue
        try:
            factory(streaming=False)
            return name
        except RuntimeError:
            continue
    return "none"