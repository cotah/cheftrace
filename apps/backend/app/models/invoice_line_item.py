from datetime import date
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field

from app.models.base import TimestampedBase
from app.models.enums import InvoiceLineItemStatus


class InvoiceLineItem(TimestampedBase, table=True):
    __tablename__ = "invoice_line_items"

    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    invoice_id: UUID = Field(foreign_key="invoices.id", nullable=False, index=True)
    line_number: int = Field(nullable=False)
    raw_text: str | None = None
    suggested_product_id: UUID | None = Field(
        default=None, foreign_key="products.id", nullable=True
    )
    confirmed_product_id: UUID | None = Field(
        default=None, foreign_key="products.id", nullable=True
    )
    quantity: Decimal | None = Field(
        default=None,
        sa_column=sa.Column(sa.NUMERIC(12, 3), nullable=True),
    )
    unit: str | None = None
    unit_cost: Decimal | None = Field(
        default=None,
        sa_column=sa.Column(sa.NUMERIC(12, 4), nullable=True),
    )
    total_cost: Decimal | None = Field(
        default=None,
        sa_column=sa.Column(sa.NUMERIC(12, 2), nullable=True),
    )
    expiry_date: date | None = None
    batch_code: str | None = None
    status: str = Field(default=InvoiceLineItemStatus.SUGGESTED, nullable=False)
    notes: str | None = None
