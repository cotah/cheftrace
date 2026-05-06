from datetime import date
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field

from app.models.base import TimestampedBase
from app.models.enums import LotStatus


class StockLot(TimestampedBase, table=True):
    __tablename__ = "stock_lots"

    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    product_id: UUID = Field(foreign_key="products.id", nullable=False, index=True)
    supplier_id: UUID | None = Field(default=None, foreign_key="suppliers.id", nullable=True)
    quantity_received: Decimal = Field(sa_column=sa.Column(sa.NUMERIC(12, 3), nullable=False))
    quantity_remaining: Decimal = Field(sa_column=sa.Column(sa.NUMERIC(12, 3), nullable=False))
    unit: str = Field(nullable=False)
    unit_cost: Decimal | None = Field(
        default=None,
        sa_column=sa.Column(sa.NUMERIC(12, 4), nullable=True),
    )
    expiry_date: date | None = Field(default=None, nullable=True)
    received_date: date = Field(default_factory=date.today, nullable=False)
    status: str = Field(default=LotStatus.ACTIVE, nullable=False)
    notes: str | None = None
    created_by_user_id: UUID = Field(foreign_key="users.id", nullable=False)
