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

FALLBACK HAQIDA (TUZATILDI):
  Avvalgi `get_llm()` faqat model OBYEKTINI yaratayotganda (factory
  chaqirilganda) `RuntimeError` chiqsa keyingi providerga o'tardi —
  ya'ni faqat "API kaliti sozlanmagan" holatini qamrardi. Agar kalit
  bor-u, lekin so'rov PAYTIDA (rate limit, tarmoq xatosi, quota
  tugashi, 500 xatolik va h.k.) muammo chiqsa, `rag.py` da
  `chain.invoke()` / `chain.astream()` bevosita chaqirilardi va bu
  holatda fallback ISHLAMASDI — xato to'g'ridan-to'g'ri foydalanuvchiga
  chiqib ketardi. Bu docstring va nomlanish va'da qilgan xatti-harakatga
  zid edi.

  Yechim: `invoke_with_fallback()` va `astream_with_fallback()` —
  bular chaqiruvni ZANJIR bo'ylab HAR BIR PROVIDER uchun alohida
  sinab ko'radi (factory yaratishda ham, so'rov chaqirilganda ham).
  Eskicha `get_llm()` ham qoldirilgan (masalan, faqat "hozir qaysi
  LLM faol" ma'lumotini bilish kerak bo'lgan joylar uchun), lekin
  RAG javob generatsiyasi endi shu ikkita yangi funksiyadan foydalanadi.

  Streaming uchun MUHIM eslatma: agar oqim (stream) allaqachon bir
  nechta token yuborib bo'lgandan keyin xato chiqsa, boshqa providerga
  "sirtdan" o'tib ketish foydalanuvchiga takrorlangan/chalkash matn
  yuborishga olib kelishi mumkin. Shuning uchun `astream_with_fallback`
  faqat OQIM HALI HECH NARSA YUBORMAGAN holatda keyingi providerga
  o'tadi; oqim boshlangandan keyin xato chiqsa — xato yuqoriga
  uzatiladi (chaqiruvchi, masalan SSE endpoint, buni foydalanuvchiga
  aniq xato sifatida ko'rsatadi, noto'g'ri/qo'shilib ketgan javob
  yubormaydi).
"""

import logging
from typing import Any, AsyncIterator, Dict, Optional

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
        model="claude-haiku-4-5-20251001",
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
        model="gemini-2.5-flash",
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


def _get_order() -> tuple[str, list]:
    from app.core.config import settings
    primary = settings.PRIMARY_LLM.lower()
    order = _FALLBACK_ORDER.get(primary, _FALLBACK_ORDER["openai"])
    return primary, order


def invoke_with_fallback(prompt, inputs: Dict[str, Any]) -> Any:
    """
    `prompt | llm` zanjirini PRIMARY_LLM dan boshlab, kerak bo'lsa
    keyingi providerlarga o'tib chaqiradi. Har bir provider uchun ham
    "model yaratish" (kalit yo'qligi), ham "haqiqiy so'rov" (rate
    limit, tarmoq xatosi va h.k.) darajasidagi xatolar ushlanadi.

    Returns:
        LangChain chat model javobi (`.content` bilan matnni olish mumkin).

    Raises:
        RuntimeError — barcha providerlar ishlamasa.
    """
    primary, order = _get_order()
    last_error: Optional[Exception] = None

    for name in order:
        factory = _LLM_FACTORIES.get(name)
        if not factory:
            continue
        try:
            llm = factory(streaming=False)
            chain = prompt | llm
            response = chain.invoke(inputs)
            if name != primary:
                logger.warning(f"LLM fallback (invoke): {primary} → {name}")
            else:
                logger.debug(f"LLM: {name} ishlatilmoqda")
            return response
        except Exception as e:
            logger.warning(f"LLM '{name}' so'rovda ishlamadi, keyingisiga o'tilmoqda: {e}")
            last_error = e
            continue

    raise RuntimeError(
        f"Hech qanday LLM javob bera olmadi. "
        f"Oxirgi xato: {last_error}. "
        f".env da kamida bitta ishlaydigan API kalit bo'lishi kerak: "
        f"OPENAI_API_KEY, ANTHROPIC_API_KEY yoki GEMINI_API_KEY"
    )


async def astream_with_fallback(prompt, inputs: Dict[str, Any]) -> AsyncIterator[str]:
    """
    `invoke_with_fallback` bilan bir xil fallback mantig'i, lekin
    streaming uchun.

    MUHIM: fallback faqat OQIM HALI BIRON TOKEN YUBORMAGAN holatda
    ishlaydi. Agar bitta provider bir nechta tokendan keyin uzilib
    qolsa, boshqa providerga o'tish o'rniga xato yuqoriga uzatiladi —
    aks holda foydalanuvchiga ikki xil javobning aralashmasi ketishi
    mumkin.
    """
    primary, order = _get_order()
    last_error: Optional[Exception] = None

    for name in order:
        factory = _LLM_FACTORIES.get(name)
        if not factory:
            continue

        started = False
        try:
            llm = factory(streaming=True)
            chain = prompt | llm
            async for chunk in chain.astream(inputs):
                if not started:
                    started = True
                    if name != primary:
                        logger.warning(f"LLM fallback (stream): {primary} → {name}")
                    else:
                        logger.debug(f"LLM: {name} ishlatilmoqda (stream)")
                if hasattr(chunk, "content") and chunk.content:
                    yield chunk.content
            return
        except Exception as e:
            if started:
                logger.error(
                    f"LLM '{name}' oqim boshlangandan keyin uzildi, "
                    f"boshqa providerga o'tilmaydi (javob chalkashib "
                    f"ketmasligi uchun): {e}"
                )
                raise
            logger.warning(f"LLM '{name}' oqimni boshlay olmadi, keyingisiga o'tilmoqda: {e}")
            last_error = e
            continue

    raise RuntimeError(
        f"Hech qanday LLM oqim (stream) boshlay olmadi. "
        f"Oxirgi xato: {last_error}. "
        f".env da kamida bitta ishlaydigan API kalit bo'lishi kerak: "
        f"OPENAI_API_KEY, ANTHROPIC_API_KEY yoki GEMINI_API_KEY"
    )