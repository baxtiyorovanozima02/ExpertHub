"""
Matnni RAG uchun kichik bo'laklarga (chunk) bo'lish logikasi.

Nega kerak: agar butun hujjat (masalan, 5000 belgili matn) bitta
embedding sifatida saqlansa, qidiruv sifati pasayadi va LLM kontekst
oynasi behuda to'lib ketadi. Shuning uchun matn kichik, bir-biriga
qisman ustma-ust tushadigan (overlap) bo'laklarga bo'linadi.
"""

from typing import List

DEFAULT_CHUNK_SIZE = 800

DEFAULT_CHUNK_OVERLAP = 100


def split_text_into_chunks(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[str]:
    """
    Matnni avval paragraflarga (bo'sh qatorlar bo'yicha), so'ng kerak
    bo'lsa belgilar soni bo'yicha chunklarga bo'ladi.

    - Juda qisqa matn (chunk_size dan kichik) -> 1 ta chunk qaytaradi.
    - Paragraflar chunk_size dan kichik bo'lsa, ular birlashtiriladi.
    - Bitta paragraf chunk_size dan katta bo'lsa, u belgilar bo'yicha
      overlap bilan bo'linadi.
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


def _split_long_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Juda uzun (paragrafsiz) matnni belgilar bo'yicha overlap bilan bo'ladi."""
    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunks.append(text[start:end].strip())
        if end == text_len:
            break
        start = end - overlap

    return chunks