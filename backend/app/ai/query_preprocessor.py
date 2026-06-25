# app/ai/query_preprocessor.py
"""
Query Preprocessing — #4

Nima qiladi:
  Foydalanuvchi "nima bu?", "ayt", "bilmadim" kabi qisqa yoki
  noaniq savollar yozganda — embedding sifatsiz bo'ladi va
  Qdrant noto'g'ri chunklar topadi.

  Bu modul savolni:
    1. Tilini aniqlab oladi (uz / ru / en)
    2. Qisqa bo'lsa — conversation history dan kontekst qo'shib to'ldiradi
    3. Imlo xatolarini tuzatmaydi (LLM ga havola qilamiz — arzon emas)
    4. Tayyor, boyitilgan savolni qaytaradi — bu embedding uchun ishlatiladi

Misol:
  Savol:   "nima bu?"
  History: ["Mehnat shartnomasi haqida gapiring", "Mehnat shartnomasi ..."]
  Natija:  "Mehnat shartnomasi nima?"

  Savol:   "срок действия?"
  Natija:  til: ru, savol o'zgarishsiz (yetarli uzunlik)
"""

import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

_SHORT_QUERY_THRESHOLD = 15

_VAGUE_PATTERNS = re.compile(
    r"^(nima bu|bu nima|ayt|bilmadim|ha|yo'q|tushunmadim|"
    r"что это|это что|скажи|не понял|"
    r"what is this|tell me|i don't know)\??\.?$",
    re.IGNORECASE,
)

_RU_PATTERN = re.compile(r"[а-яёА-ЯЁ]")
_EN_PATTERN = re.compile(r"^[a-zA-Z\s\d\W]+$")


def detect_language(text: str) -> str:
    """
    Matn tilini aniqlaydi.
    Returns: 'uz' | 'ru' | 'en'
    """
    if _RU_PATTERN.search(text):
        return "ru"
    if _EN_PATTERN.match(text.strip()):
        return "en"
    return "uz"


def expand_query(
    question: str,
    history: Optional[List] = None,
) -> str:
    """
    Savolni boyitadi:
      - Qisqa yoki noaniq bo'lsa, history dan oxirgi mavzuni qo'shadi
      - Yetarli uzunlikda bo'lsa — o'zgarishsiz qaytaradi

    Args:
        question: Foydalanuvchi savoli
        history:  Message obyektlari ro'yxati (oxirgisi birinchi bo'lishi shart emas)

    Returns:
        Boyitilgan savol matni
    """
    question = question.strip()

    if not question:
        return question

    is_short = len(question) < _SHORT_QUERY_THRESHOLD
    is_vague = bool(_VAGUE_PATTERNS.match(question))

    if not (is_short or is_vague):
        return question

    if not history:
        return question

    last_topic = ""
    for msg in reversed(history):
        if hasattr(msg, "role") and msg.role == "user":
            if len(msg.content.strip()) >= _SHORT_QUERY_THRESHOLD:
                last_topic = msg.content.strip()
                break

    if not last_topic:
        return question

    expanded = f"{last_topic} — {question}"
    logger.info(
        f"Query expanded: '{question}' -> '{expanded}'"
    )
    return expanded