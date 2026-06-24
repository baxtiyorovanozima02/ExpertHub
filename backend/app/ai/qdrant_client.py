"""
Qdrant vector bazasi bilan ishlash uchun yordamchi modul.

Nega kerak: avval embeddinglar Postgres ichida (pgvector extension)
saqlanardi. Endi vector qidiruv alohida Qdrant konteynerida ishlaydi -
bu Postgres'ni faqat relyatsion ma'lumotlar uchun ishlatishga, vector
qidiruvni esa shu vazifaga ixtisoslashgan tezkor bazaga ajratishga
imkon beradi.

Ikki bosqichli (coarse-to-fine) qidiruv:
  Agar hujjatlar va chunklar soni katta bo'lsa, har bir savol uchun
  BARCHA chunklarni solishtirish sekinlashadi (1000 ta so'z ichidan
  "nozima" so'zini har birini taqqoslab qidirish kabi).

  Shuning uchun ikkita kolleksiya ishlatiladi:
    1. `QDRANT_COLLECTION_NAME` (chunklar)        - har bir chunk uchun vektor
    2. `QDRANT_DOCUMENT_COLLECTION_NAME` (hujjatlar) - har bir hujjat uchun
       "markaziy vektor" (centroid) - shu hujjatdagi barcha chunk
       vektorlarining o'rtachasi

  Qidiruv 2 bosqichda boradi:
    1-bosqich (tez, tor doira): savol vektori hujjat centroidlari bilan
       solishtiriladi -> eng mos N ta hujjat topiladi
       (so'zlarni "n" harfi bo'yicha bo'lakka ajratish kabi)
    2-bosqich (aniq): faqat shu N ta hujjatning chunklari orasidan
       eng yaqin chunklar qidiriladi
       (endi faqat "n" bilan boshlanadigan so'zlar ichidan "nozima"ni qidirish)

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

DEFAULT_DOCUMENT_TOP_K = 5

_DOCUMENT_COLLECTION_NAME = getattr(
    settings, "QDRANT_DOCUMENT_COLLECTION_NAME", "expert_documents_centroids"
)

_client: Optional[QdrantClient] = None


def get_client() -> QdrantClient:
    """Qdrant klientini (singleton) qaytaradi va kolleksiyalar mavjudligini ta'minlaydi."""
    global _client
    if _client is None:
        _client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        _ensure_collection(_client)
        _ensure_document_collection(_client)
    return _client


def _ensure_collection(client: QdrantClient) -> None:
    """Chunk vektorlari uchun asosiy kolleksiya."""
    existing = [c.name for c in client.get_collections().collections]
    if settings.QDRANT_COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            vectors_config=qmodels.VectorParams(
                size=EMBEDDING_DIM,
                distance=qmodels.Distance.COSINE,
            ),
        )


def _ensure_document_collection(client: QdrantClient) -> None:
    """
    Hujjatlarning "markaziy vektori" (centroid) uchun alohida, kichik
    kolleksiya. Bu kolleksiya har doim chunk kolleksiyasidan ancha
    kichik bo'ladi (hujjatlar soni << chunklar soni), shu sababli
    1-bosqich qidiruvi juda tez bo'ladi.
    """
    existing = [c.name for c in client.get_collections().collections]
    if _DOCUMENT_COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=_DOCUMENT_COLLECTION_NAME,
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


def upsert_document_centroid(
    document_id: int,
    chunk_vectors: List[List[float]],
    category_id: Optional[int] = None,
) -> None:
    """
    Hujjatning barcha chunk vektorlaridan o'rtacha (centroid) vektor
    hisoblab, alohida hujjatlar-kolleksiyasiga yozadi.

    Bu funksiya hujjat har safar qayta embed qilinganda (yangi fayl
    yuklanganda yoki tahrirlanganda) chaqirilishi kerak, chunki
    centroid o'zgargan chunklar bilan birga o'zgaradi.
    """
    if not chunk_vectors:
        return

    dim = len(chunk_vectors[0])
    centroid = [
        sum(vec[i] for vec in chunk_vectors) / len(chunk_vectors)
        for i in range(dim)
    ]

    client = get_client()
    client.upsert(
        collection_name=_DOCUMENT_COLLECTION_NAME,
        points=[
            qmodels.PointStruct(
                id=document_id,
                vector=centroid,
                payload={
                    "document_id": document_id,
                    "category_id": category_id,
                },
            )
        ],
    )


def delete_document_centroid(document_id: int) -> None:
    """Hujjat o'chirilganda uning centroidini ham o'chiradi."""
    client = get_client()
    client.delete(
        collection_name=_DOCUMENT_COLLECTION_NAME,
        points_selector=qmodels.PointIdsList(points=[document_id]),
    )


def _build_category_filter(category_id: Optional[int]) -> Optional[qmodels.Filter]:
    if category_id is None:
        return None
    return qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="category_id",
                match=qmodels.MatchValue(value=category_id),
            )
        ]
    )


def search_similar_documents(
    query_vector: List[float],
    category_id: Optional[int] = None,
    top_k: int = DEFAULT_DOCUMENT_TOP_K,
) -> List[int]:
    """
    1-BOSQICH (tor doirani topish): savol vektoriga eng yaqin
    `top_k` ta hujjat_id'ni qaytaradi. Bu hujjatlar centroidlari
    bo'yicha solishtirish orqali bo'ladi, shuning uchun juda tez.
    """
    client = get_client()
    results = client.query_points(
        collection_name=_DOCUMENT_COLLECTION_NAME,
        query=query_vector,
        query_filter=_build_category_filter(category_id),
        limit=top_k,
    ).points
    return [point.id for point in results]


def search_similar_chunks(
    query_vector: List[float],
    category_id: Optional[int] = None,
    document_ids: Optional[List[int]] = None,
    top_k: int = 5,
) -> List[int]:
    """
    2-BOSQICH (aniq qidiruv): berilgan vektorga eng yaqin chunk_id'larni
    qaytaradi.

    - category_id berilgan bo'lsa, faqat shu kategoriyadagi chunklar
      orasidan qidiriladi.
    - document_ids berilgan bo'lsa (1-bosqichda tanlangan "tor doira"),
      qidiruv FAQAT shu hujjatlarning chunklari orasida bajariladi -
      bu butun kolleksiyani emas, kichik bir qismini skanerlash demakdir.
    """
    client = get_client()

    must_conditions = []
    if category_id is not None:
        must_conditions.append(
            qmodels.FieldCondition(
                key="category_id",
                match=qmodels.MatchValue(value=category_id),
            )
        )
    if document_ids:
        must_conditions.append(
            qmodels.FieldCondition(
                key="document_id",
                match=qmodels.MatchAny(any=document_ids),
            )
        )

    query_filter = qmodels.Filter(must=must_conditions) if must_conditions else None

    results = client.query_points(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        query=query_vector,
        query_filter=query_filter,
        limit=top_k,
    ).points

    return [point.id for point in results]