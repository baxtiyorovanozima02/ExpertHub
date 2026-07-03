from typing import List, Optional
import logging

from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk
from app.ai.embeddings import generate_embedding
from app.ai import qdrant_client
from app.ai.keyword_search import keyword_search_chunk_ids
from app.core.config import settings

logger = logging.getLogger(__name__)


_RRF_K = 60


def _reciprocal_rank_fusion(ranked_lists: List[List[int]], top_k: int) -> List[int]:
    """
    Bir nechta reytinglangan ro'yxatlarni (masalan: vektor qidiruv
    natijalari va kalit so'z qidiruv natijalari) bitta umumiy
    reytingga birlashtiradi.

    Formula har bir element uchun: score += 1 / (K + rank + 1)
    - Element ro'yxat boshida bo'lsa (rank kichik) -> ball yuqori.
    - Element ikkala ro'yxatda ham bo'lsa -> ballari qo'shiladi,
      demak ikkala usul ham "rozi" bo'lgan natijalar tepaga chiqadi.
    - Ballarni normalizatsiya qilish shart emas (masalan, vektor
      cosine-similarity va ts_rank butunlay boshqa shkalada bo'lsa
      ham), chunki faqat RANK (o'rin), qiymat emas, hisobga olinadi.
    """
    scores: dict[int, float] = {}
    for ranked_list in ranked_lists:
        for rank, item_id in enumerate(ranked_list):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (_RRF_K + rank + 1)

    fused = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
    return [item_id for item_id, _ in fused[:top_k]]


def find_relevant_chunks(
    db: Session,
    query_text: str,
    category_id: Optional[int] = None,
    top_k: int = 5,
    document_top_k: int = qdrant_client.DEFAULT_DOCUMENT_TOP_K,
    use_hybrid: bool = True,
) -> List[DocumentChunk]:
    """
    HYBRID SEARCH: ikki bosqichli (coarse-to-fine) vektor qidiruv +
    kalit so'z (full-text) qidiruv, Reciprocal Rank Fusion bilan
    birlashtirilgan.

    1-BOSQICH (tor doira): savol vektori hujjatlarning "markaziy
       vektori" (centroid) bilan solishtiriladi -> eng mos
       `document_top_k` ta hujjat topiladi (butun chunklar to'plamini
       emas, faqat hujjatlar sonini skanerlaydi - ancha tezkor).

    2-BOSQICH (aniq qidiruv, HYBRID): shu tanlangan hujjatlar ichida
       ikkita mustaqil qidiruv parallel bajariladi:
         a) Vektor (semantik) qidiruv — Qdrant orqali, "ma'no"
            bo'yicha o'xshashlik.
         b) Kalit so'z (leksik) qidiruv — Postgres full-text search
            orqali, aniq atama/ID/raqamlarni topish uchun kuchli.
       Ikkala natija RRF orqali bitta reytingga birlashtiriladi.

    Agar 1-bosqichda hech qanday hujjat topilmasa, avtomatik ravishda
    butun chunklar to'plami bo'yicha qidiruvga qaytadi (fallback) —
    xuddi avvalgidek.

    use_hybrid=False qilib chaqirsangiz, faqat vektor qidiruv
    ishlatiladi (eski xatti-harakat).
    """
    query_vector = generate_embedding(query_text)

    candidate_document_ids = qdrant_client.search_similar_documents(
        query_vector=query_vector,
        category_id=category_id,
        top_k=document_top_k,
    )


    fetch_k = max(top_k * 2, top_k + 5)

    vector_chunk_ids = qdrant_client.search_similar_chunks(
        query_vector=query_vector,
        category_id=category_id,
        document_ids=candidate_document_ids or None,
        top_k=fetch_k,
    )

    if not vector_chunk_ids and candidate_document_ids:
        vector_chunk_ids = qdrant_client.search_similar_chunks(
            query_vector=query_vector,
            category_id=category_id,
            document_ids=None,
            top_k=fetch_k,
        )

    keyword_chunk_ids: List[int] = []
    hybrid_enabled = use_hybrid and getattr(settings, "HYBRID_SEARCH_ENABLED", True)
    if hybrid_enabled:
        try:
            keyword_chunk_ids = keyword_search_chunk_ids(
                db,
                query_text,
                category_id=category_id,
                document_ids=candidate_document_ids or None,
                top_k=fetch_k,
            )
        except Exception as exc:
            logger.warning(
                "Kalit so'z qidiruvi ishlamadi, faqat vektor natijalar "
                "ishlatiladi: %s", exc
            )
            keyword_chunk_ids = []

    fused_ids = _reciprocal_rank_fusion(
        [vector_chunk_ids, keyword_chunk_ids], top_k=top_k
    )

    if not fused_ids:
        return []

    chunks = db.query(DocumentChunk).filter(DocumentChunk.id.in_(fused_ids)).all()

    order = {chunk_id: i for i, chunk_id in enumerate(fused_ids)}
    chunks.sort(key=lambda c: order.get(c.id, len(fused_ids)))

    return chunks