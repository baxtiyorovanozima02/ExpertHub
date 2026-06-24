"""
Qdrant vector bazasi bilan ishlash uchun yordamchi modul.

Nega kerak: avval embeddinglar Postgres ichida (pgvector extension)
saqlanardi. Endi vector qidiruv alohida Qdrant konteynerida ishlaydi -
bu Postgres'ni faqat relyatsion ma'lumotlar uchun ishlatishga, vector
qidiruvni esa shu vazifaga ixtisoslashgan tezkor bazaga ajratishga
imkon beradi.

Har bir nuqta (point) Qdrant'da quyidagicha saqlanadi:
  - id: DocumentChunk.id (Postgres'dagi chunk bilan bog'lash uchun)
  - vector: 384 o'lchamli embedding
  - payload: chunk_id, document_id, category_id (filtrlash uchun)
"""

from typing import List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import settings

EMBEDDING_DIM = 384

_client: Optional[QdrantClient] = None


def get_client() -> QdrantClient:
    """Qdrant klientini (singleton) qaytaradi va kolleksiya mavjudligini ta'minlaydi."""
    global _client
    if _client is None:
        _client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        _ensure_collection(_client)
    return _client


def _ensure_collection(client: QdrantClient) -> None:
    existing = [c.name for c in client.get_collections().collections]
    if settings.QDRANT_COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            vectors_config=qmodels.VectorParams(
                size=EMBEDDING_DIM,
                distance=qmodels.Distance.COSINE,
            ),
        )


def upsert_chunk_embedding(
    chunk_id: int,
    vector: List[float],
    document_id: int,
    category_id: Optional[int] = None,
) -> None:
    """Bitta chunk uchun embeddingni Qdrant'ga yozadi (yoki yangilaydi)."""
    client = get_client()
    client.upsert(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        points=[
            qmodels.PointStruct(
                id=chunk_id,
                vector=vector,
                payload={
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "category_id": category_id,
                },
            )
        ],
    )


def delete_chunk_embedding(chunk_id: int) -> None:
    """Chunk o'chirilganda Qdrant'dagi mos nuqtani ham o'chiradi."""
    client = get_client()
    client.delete(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        points_selector=qmodels.PointIdsList(points=[chunk_id]),
    )


def search_similar_chunks(
    query_vector: List[float],
    category_id: Optional[int] = None,
    top_k: int = 5,
) -> List[int]:
    """
    Berilgan vektorga eng yaqin chunk_id'larni qaytaradi.
    category_id berilgan bo'lsa, faqat shu kategoriyadagi chunklar orasidan qidiriladi.
    """
    client = get_client()

    query_filter = None
    if category_id is not None:
        query_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="category_id",
                    match=qmodels.MatchValue(value=category_id),
                )
            ]
        )

    results = client.query_points(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        query=query_vector,
        query_filter=query_filter,
        limit=top_k,
    ).points

    return [point.id for point in results]