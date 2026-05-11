from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field

from app.models.base import TimestampedBase
from app.models.enums import InvoiceStatus


class Invoice(TimestampedBase, table=True):
    __tablename__ = "invoices"
    # Mirror CHECK constraint from migration 008 so the pytest fixture
    # (SQLModel.metadata.create_all) enforces it like alembic does.
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('uploaded','processing','needs_review','confirmed','rejected')",
            name="ck_invoices_status",
        ),
    )

    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    supplier_id: UUID | None = Field(default=None, foreign_key="suppliers.id", nullable=True)
    file_path: str = Field(nullable=False)
    status: str = Field(default=InvoiceStatus.UPLOADED, nullable=False)
    uploaded_by_user_id: UUID = Field(foreign_key="users.id", nullable=False)
    processed_at: datetime | None = None
    confirmed_at: datetime | None = None
    supplier_name_raw: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    total_amount: Decimal | None = Field(
        default=None,
        sa_column=sa.Column(sa.NUMERIC(12, 2), nullable=True),
    )
    vat_amount: Decimal | None = Field(
        default=None,
        sa_column=sa.Column(sa.NUMERIC(12, 2), nullable=True),
    )
    raw_ocr_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=sa.Column(sa.JSON, nullable=True),
    )
    notes: str | None = None
