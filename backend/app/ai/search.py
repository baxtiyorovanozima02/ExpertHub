from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk
from app.ai.embeddings import generate_embedding
from app.ai import qdrant_client


def find_relevant_chunks(
    db: Session,
    query_text: str,
    category_id: Optional[int] = None,
    top_k: int = 5,
    document_top_k: int = qdrant_client.DEFAULT_DOCUMENT_TOP_K,
) -> List[DocumentChunk]:
    """
    Ikki bosqichli (coarse-to-fine) qidiruv.

    Misol: 1000 ta so'z ichidan "nozima" so'zini qidirish sekin -
    har birini birma-bir solishtirish kerak. Lekin avval so'zlarni
    "n" harfi bo'yicha bo'lakka ajratib, keyin faqat shu bo'lak
    ichidan qidirilsa, tezroq bo'ladi.

    Xuddi shunday:
      1-BOSQICH (tor doira): savol vektori hujjatlarning "markaziy
         vektori" (centroid) bilan solishtiriladi -> eng mos
         `document_top_k` ta hujjat topiladi. Bu butun chunklar
         to'plamini emas, faqat hujjatlar sonini skanerlaydi -
         ancha kichik va tezkor.
      2-BOSQICH (aniq qidiruv): faqat shu tanlangan hujjatlarning
         chunklari orasidan eng yaqin `top_k` ta chunk topiladi.

    Agar 1-bosqichda hech qanday hujjat topilmasa (masalan, hujjatlar
    kolleksiyasi bo'sh bo'lsa), avtomatik ravishda eski usulga -
    butun chunklar to'plami bo'yicha qidiruvga qaytadi (fallback).
    """
    query_vector = generate_embedding(query_text)

    candidate_document_ids = qdrant_client.search_similar_documents(
        query_vector=query_vector,
        category_id=category_id,
        top_k=document_top_k,
    )

    chunk_ids = qdrant_client.search_similar_chunks(
        query_vector=query_vector,
        category_id=category_id,
        document_ids=candidate_document_ids or None,
        top_k=top_k,
    )


    if not chunk_ids and candidate_document_ids:
        chunk_ids = qdrant_client.search_similar_chunks(
            query_vector=query_vector,
            category_id=category_id,
            document_ids=None,
            top_k=top_k,
        )

    if not chunk_ids:
        return []

    chunks = db.query(DocumentChunk).filter(DocumentChunk.id.in_(chunk_ids)).all()

    order = {chunk_id: i for i, chunk_id in enumerate(chunk_ids)}
    chunks.sort(key=lambda c: order.get(c.id, len(chunk_ids)))

    return chunks