"""
app/ai/reranking.py

CrossEncoder yordamida reranking.

Nima qiladi:
  Qdrant 8 ta chunk topadi (coarse) -> CrossEncoder ularni qayta
  baholaydi -> eng mos 3 tasini qaytaradi. Javob sifati sezilarli oshadi.

Nega CrossEncoder:
  Bi-encoder (embedding) tezkor lekin sifatda yo'qotish bor, chunki
  savol va matn alohida-alohida vektorlanadi.
  CrossEncoder esa savol + matn BIRGA ko'rib, chuqurroq munosabatni
  o'lchaydi — aniqlik oshadi.

Model:
  'cross-encoder/ms-marco-MiniLM-L-6-v2' — kichik (80MB), tez,
  production uchun yetarli sifat.
"""

from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)

_reranker = None


def _get_reranker():
    """Lazy init — birinchi chaqiruvda yuklanadi."""
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
            _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            logger.info("CrossEncoder reranker yuklandi.")
        except Exception as e:
            logger.warning(f"CrossEncoder yuklanmadi: {e}. Reranking o'tkazib yuboriladi.")
            _reranker = False
    return _reranker


def rerank_chunks(
    query: str,
    chunks,
    top_k: int = 3,
) -> list:
    """
    Chunklarni CrossEncoder bilan qayta tartiblaydi va eng yaxshi
    top_k tasini qaytaradi.

    Args:
        query:  Foydalanuvchi savoli
        chunks: DocumentChunk obyektlari ro'yxati (qdrant_client dan keladi)
        top_k:  Qaytariladigan chunk soni (default: 3)

    Returns:
        Qayta tartiblangan va qisqartirilgan chunks ro'yxati.
        CrossEncoder ishlamasa — kirgan ro'yxatning dastlabki top_k sini qaytaradi.
    """
    if not chunks:
        return []

    reranker = _get_reranker()

    if not reranker:
        logger.warning("Reranker yo'q, oddiy top_k bilan qaytarilmoqda.")
        return chunks[:top_k]

    try:
        pairs: List[Tuple[str, str]] = [(query, chunk.content) for chunk in chunks]
        scores = reranker.predict(pairs)

        scored = sorted(zip(scores, chunks), key=lambda x: x[0], reverse=True)
        best = [chunk for _, chunk in scored[:top_k]]

        logger.info(
            f"Reranking: {len(chunks)} chunk -> top {top_k}. "
            f"Eng yuqori score: {scored[0][0]:.3f}"
        )
        return best

    except Exception as e:
        logger.error(f"Reranking xatosi: {e}. Fallback: top_k.")
        return chunks[:top_k]