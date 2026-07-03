# app/ai/keyword_search.py
"""
Kalit so'z (leksik/full-text) qidiruv — Hybrid Search'ning ikkinchi yarmi.

Nega kerak:
  Vektor (semantik) qidiruv "ma'no" bo'yicha o'xshashlikni topadi, lekin
  aniq atamalar, qisqartmalar, raqamlar, ID'lar yoki kam uchraydigan
  so'zlarni ko'pincha "sezmaydi" (masalan: "INN 12345678" yoki
  "43-modda"). Kalit so'z qidiruvi esa aynan shu holatlarda kuchli.

  Hybrid Search ikkalasini birlashtiradi: vektor qidiruv + kalit so'z
  qidiruv natijalari Reciprocal Rank Fusion (RRF) orqali qo'shiladi
  (bu app/ai/search.py da amalga oshirilgan).

Qanday ishlaydi:
  PostgreSQL'ning o'rnatilgan full-text search funksiyalaridan
  foydalaniladi (to_tsvector / plainto_tsquery / ts_rank). Bu hech
  qanday yangi ustun yoki migratsiya talab qilmaydi — hisoblash
  so'rov vaqtida (on-the-fly) bajariladi. 'simple' konfiguratsiyasi
  ishlatiladi, chunki u tilga xos stemming qilmaydi va shu sababli
  o'zbek/rus/ingliz aralash matnlar uchun ham barqaror ishlaydi.

  Diqqat: DocumentChunk jadvalida category_id maydoni yo'q — u
  Expert jadvalida saqlanadi. Shuning uchun kategoriya bo'yicha
  filtrlashda DocumentChunk -> ExpertDocument -> Expert zanjiri
  bo'ylab JOIN qilinadi.

Katta hujjatlar to'plamida tezlikni oshirish uchun ixtiyoriy:
  CREATE INDEX ix_document_chunks_content_fts
  ON document_chunks USING GIN (to_tsvector('simple', content));
  (Bu shart emas — funksiya indekssiz ham to'g'ri ishlaydi, faqat
  juda katta hajmda sekinroq bo'lishi mumkin.)
"""

import logging
from typing import List, Optional

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk
from app.models.expert_document import ExpertDocument
from app.models.expert import Expert

logger = logging.getLogger(__name__)

_TS_CONFIG = "simple"


def keyword_search_chunk_ids(
    db: Session,
    query_text: str,
    category_id: Optional[int] = None,
    document_ids: Optional[List[int]] = None,
    top_k: int = 10,
) -> List[int]:
    """
    Berilgan matn bo'yicha eng mos chunk_id'larni (ts_rank bo'yicha
    kamayish tartibida) qaytaradi.

    Har qanday xatolik (masalan, DB PostgreSQL bo'lmasa, yoki so'rov
    bo'sh/noto'g'ri bo'lsa) yutib yuboriladi va bo'sh ro'yxat
    qaytariladi — bu vektor qidiruvni hech qachon buzmaydi, hybrid
    qidiruv shunchaki "faqat vektor" rejimiga tushib qoladi.
    """
    query_text = (query_text or "").strip()
    if not query_text:
        return []

    try:
        ts_query = func.plainto_tsquery(_TS_CONFIG, query_text)
        ts_vector = func.to_tsvector(_TS_CONFIG, func.coalesce(DocumentChunk.content, ""))
        rank = func.ts_rank(ts_vector, ts_query)

        q = db.query(DocumentChunk.id).join(
            ExpertDocument, ExpertDocument.id == DocumentChunk.document_id
        )

        conditions = [ts_vector.op("@@")(ts_query)]

        if document_ids:
            conditions.append(DocumentChunk.document_id.in_(document_ids))

        if category_id is not None:
            q = q.join(Expert, Expert.id == ExpertDocument.expert_id)
            conditions.append(Expert.category_id == category_id)

        rows = (
            q.filter(and_(*conditions))
            .order_by(rank.desc())
            .limit(top_k)
            .all()
        )

        return [row[0] for row in rows]

    except Exception as exc:
        logger.warning(
            "Kalit so'z (full-text) qidiruvda xatolik, faqat vektor "
            "qidiruv natijalari ishlatiladi: %s", exc
        )
        return []