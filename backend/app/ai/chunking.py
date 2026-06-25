"""
Matnni RAG uchun kichik bo'laklarga (chunk) bo'lish logikasi.

Nega kerak: agar butun hujjat (masalan, 5000 belgili matn) bitta
embedding sifatida saqlansa, qidiruv sifati pasayadi va LLM kontekst
oynasi behuda to'lib ketadi. Shuning uchun matn kichik, bir-biriga
qisman ustma-ust tushadigan (overlap) bo'laklarga bo'linadi.

Yaxshilanish (gap chegarasida kesish):
  Avvalgi versiyada matn aynan chunk_size belgida kesilardi — gap
  o'rtasida ham. Bu LLM uchun chalkash, chunki gap yarim qoladi.

  Yangi versiyada:
    1. Avval paragraflar bo'yicha bo'linadi (o'zgarmadi).
    2. Uzun paragraf kesilganda — eng yaqin gap oxiri (". ") yoki
       qator oxiri ("\n") topiladi va o'sha joyda to'xtatiladi.
    3. Agar hech qanday gap/qator topilmasa — eski usulga qaytadi
       (belgi soni bo'yicha), xato bermaydi.
"""

import re
from typing import List

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 100

_SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+')


def split_text_into_chunks(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[str]:
    """
    Matnni avval paragraflarga (bo'sh qatorlar bo'yicha), so'ng kerak
    bo'lsa gap chegarasiga qarab chunklarga bo'ladi.

    - Juda qisqa matn (chunk_size dan kichik)  -> 1 ta chunk qaytaradi.
    - Paragraflar chunk_size dan kichik bo'lsa, ular birlashtiriladi.
    - Bitta paragraf chunk_size dan katta bo'lsa, u GAP CHEGARASIDA
      overlap bilan bo'linadi (avval ". ", keyin "\n", oxirgi chora
      sifatida belgi soni bo'yicha).
    """
    text = text.strip()
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: List[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_long_text(paragraph, chunk_size, overlap))
            continue

        if not current:
            current = paragraph
        elif len(current) + 2 + len(paragraph) <= chunk_size:
            current = f"{current}\n\n{paragraph}"
        else:
            chunks.append(current.strip())
            current = paragraph

    if current:
        chunks.append(current.strip())

    return chunks


def _find_sentence_boundary(text: str, start: int, end: int) -> int:
    """
    [start, end] oralig'ida eng oxirgi gap chegarasini topadi.

    Ustuvorlik tartibi:
      1. ". "  — gap oxiri (nuqta + bo'sh joy)
      2. "! "  — undov gap oxiri
      3. "? "  — so'roq gap oxiri
      4. "\n"  — qator oxiri
      5. topilmasa — -1 qaytaradi (belgi soni bo'yicha kesish)

    Misol:
      text = "Ali keldi. Vali ketdi. Aziz..."
      start=0, end=20
      -> "Ali keldi. " oxiri topiladi -> 10 qaytadi
    """
    window = text[start:end]

    for pattern in (". ", "! ", "? "):
        pos = window.rfind(pattern)
        if pos != -1:
            return start + pos + len(pattern)

    pos = window.rfind("\n")
    if pos != -1:
        return start + pos + 1

    return -1


def _split_long_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """
    Uzun matnni gap chegarasida overlap bilan bo'ladi.

    Har bir chunkda:
      1. [start, start+chunk_size] oralig'ida gap chegarasi qidiriladi.
      2. Topilsa — o'sha joyda to'xtatiladi (gap o'rtasida kesilmaydi).
      3. Topilmasa — eski usul: aynan chunk_size da kesiladi.
      4. Keyingi chunk overlap qadar orqaga qaytib boshlanadi.
    """
    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        if end < text_len:
            boundary = _find_sentence_boundary(text, start, end)
            if boundary != -1 and boundary > start:
                end = boundary

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end == text_len:
            break

        overlap_start = max(start, end - overlap)
        boundary = _find_sentence_boundary(text, overlap_start, end)
        start = boundary if (boundary != -1 and boundary > overlap_start) else overlap_start

    return chunks