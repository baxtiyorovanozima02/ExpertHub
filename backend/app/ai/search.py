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
) -> List[DocumentChunk]:
    """
    Savol matni uchun embedding hosil qiladi, Qdrant orqali eng yaqin
    `top_k` ta chunk_id'ni topadi, so'ng mos DocumentChunk yozuvlarini
    (matnini) Postgres'dan o'qib qaytaradi.

    Eslatma: vector qidiruv endi Postgres'da emas, alohida Qdrant
    konteynerida bajariladi. Postgres faqat chunk matnini saqlaydi.

    Agar category_id berilgan bo'lsa, faqat shu kategoriyadagi ekspertlar
    hujjatlari orasidan qidiriladi (Qdrant payload filtri orqali).
    """
    query_vector = generate_embedding(query_text)

    chunk_ids = qdrant_client.search_similar_chunks(
        query_vector=query_vector,
        category_id=category_id,
        top_k=top_k,
    )

    if not chunk_ids:
        return []

    chunks = db.query(DocumentChunk).filter(DocumentChunk.id.in_(chunk_ids)).all()

    order = {chunk_id: i for i, chunk_id in enumerate(chunk_ids)}
    chunks.sort(key=lambda c: order.get(c.id, len(chunk_ids)))

    return chunks