"""fix expert_documents.created_at default

Muammo: expert_documents jadvali yaratilgan migratsiyada (b18ca1779f63)
created_at ustuni uchun server_default belgilanmagan edi, garchi
SQLAlchemy modelida (app/models/expert_document.py) server_default=func.now()
yozilgan bo'lsa ham. Natijada bazaga yozilgan har bir yangi hujjatda
created_at qiymati NULL bo'lib qolar, buning natijasida
ExpertDocumentOut (pydantic) javob qaytarishda quyidagi xatoni berardi:

    pydantic_core._pydantic_core.ValidationError: 1 validation error
    for ExpertDocumentOut
    created_at
      Input should be a valid datetime [type=datetime_type, input_value=None]

Bu migratsiya:
  1. Mavjud NULL qiymatlarni joriy vaqt bilan to'ldiradi
  2. Ustunga DB darajasida server_default (CURRENT_TIMESTAMP) qo'yadi
  3. Ustunni NOT NULL qilib belgilaydi

Revision ID: h1i2j3k4l5m6
Revises: a1b2c3d4e5f6
Create Date: 2026-07-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'h1i2j3k4l5m6'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE expert_documents SET created_at = NOW() WHERE created_at IS NULL"
    )


    op.alter_column(
        'expert_documents',
        'created_at',
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text('now()'),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'expert_documents',
        'created_at',
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        nullable=True,
    )