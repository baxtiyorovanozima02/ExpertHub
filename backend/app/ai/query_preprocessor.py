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

TIL ANIQLASH HAQIDA (TUZATILDI):
  Avvalgi versiyada ingliz tili "^[a-zA-Z\\s\\d\\W]+$" pattern bilan
  aniqlanardi — bu HAR QANDAY lotin yozuvidagi matnga (imlosidan
  qat'iy nazar) mos kelardi, chunki \\W klassi kirill bo'lmagan barcha
  belgilarni "so'z bo'lmagan belgi" deb hisoblaydi. Natijada lotin
  yozuvidagi o'zbekcha savollarning DEYARLI HAMMASI "en" deb noto'g'ri
  aniqlanardi (masalan: "Mehnat shartnomasi qanday tuziladi?" -> "en").

  Yangi yechim — engil, tashqi kutubxonasiz so'z-chastotasi asosidagi
  heuristika:
    1. Kirill harfi bo'lsa -> "ru" (bu holat aniq va ishonchli).
    2. Aks holda matn so'zlarga bo'linadi va har bir so'z o'zbekcha
       va inglizcha eng ko'p uchraydigan funksional so'zlar (stopword)
       ro'yxati bilan solishtiriladi.
    3. "o'" / "g'" kabi faqat o'zbek tiliga xos harf birikmalari
       aniqlansa, bu kuchli o'zbekcha signal sifatida qo'shimcha
       ball beradi (inglizchada deyarli uchramaydi).
    4. Ball tortishuvida yoki hech qanday mos so'z topilmasa,
       platformaning asosiy tili bo'lgan "uz" ga qaytiladi (xavfsiz
       default — noaniq holatda foydalanuvchi tilini "en" deb
       taxmin qilishdan ko'ra ona tiliga qaytish to'g'riroq).

  Bu yechim 3 ta aniq tilni ajratish uchun yetarli va production'da
  qo'shimcha ML modeli/tarmoq so'rovisiz ishlaydi. Agar kelajakda
  boshqa tillar (masalan, qozoq, tojik) qo'shilsa — bu yerga alohida
  stopword ro'yxati va/yoki 'langdetect' kabi kutubxona qo'shish
  tavsiya etiladi.
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

_WORD_PATTERN = re.compile(r"[a-zA-Z']+")


_APOSTROPHE_VARIANTS = str.maketrans({
    "\u2018": "'",
    "\u2019": "'",
    "\u02bb": "'",
    "\u02bc": "'",
    "`":      "'",
})

_UZ_STOPWORDS = {
    "bu", "shu", "u", "va", "yoki", "ham", "faqat", "emas", "yo'q",
    "bor", "kerak", "uchun", "bilan", "qanday", "qachon", "qayerda",
    "qayerdan", "nega", "nima", "nimaga", "kim", "qaysi", "qancha",
    "necha", "qay", "bo'ladi", "bo'lsa", "bo'lgan", "edi", "ekan",
    "men", "siz", "biz", "ular", "sen", "meni", "sizni", "bizni",
    "uni", "unga", "menga", "sizga", "bizga", "haqida", "tartibi",
    "tartib", "muddat", "muddati", "qanaqa", "qilib", "qiladi",
    "qilingan", "bo'yicha", "hozir", "keyin", "oldin", "endi",
}

_EN_STOPWORDS = {
    "the", "is", "are", "was", "were", "what", "how", "when", "where",
    "why", "who", "which", "this", "that", "these", "those", "with",
    "for", "and", "or", "not", "do", "does", "did", "can", "could",
    "should", "would", "will", "have", "has", "had", "i", "you", "we",
    "they", "it", "he", "she", "a", "an", "of", "to", "in", "on", "at",
    "be", "been", "being", "please", "tell", "me", "about",
    "hello", "hi", "hey", "thanks", "thank", "yes", "no", "ok", "okay",
}


_UZ_ONLY_DIGRAPH = re.compile(r"[og]'", re.IGNORECASE)


def detect_language(text: str) -> str:
    """
    Matn tilini aniqlaydi.
    Returns: 'uz' | 'ru' | 'en'

    Kirill harfi topilsa — darhol "ru". Aks holda so'z-chastotasi
    heuristikasi orqali "uz" yoki "en" tanlanadi (default: "uz").
    """
    if not text or not text.strip():
        return "uz"

    if _RU_PATTERN.search(text):
        return "ru"

    normalized = text.strip().lower().translate(_APOSTROPHE_VARIANTS)
    words = set(_WORD_PATTERN.findall(normalized))

    if not words:
        return "uz"

    uz_score = len(words & _UZ_STOPWORDS)
    en_score = len(words & _EN_STOPWORDS)

    if _UZ_ONLY_DIGRAPH.search(normalized):
        uz_score += 2

    if en_score > uz_score:
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