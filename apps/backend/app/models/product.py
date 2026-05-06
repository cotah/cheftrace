from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field

from app.models.base import TimestampedBase


class Product(TimestampedBase, table=True):
    __tablename__ = "products"

    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    category_id: UUID | None = Field(
        default=None, foreign_key="product_categories.id", nullable=True
    )
    name: str = Field(nullable=False)
    sku: str | None = None
    unit: str = Field(nullable=False)
    unit_cost: Decimal | None = Field(
        default=None,
        sa_column=sa.Column(sa.NUMERIC(12, 4), nullable=True),
    )
    minimum_stock_quantity: Decimal | None = Field(
        default=None,
        sa_column=sa.Column(sa.NUMERIC(12, 3), nullable=True),
    )
    expiry_required: bool = Field(default=False)
    storage_type: str | None = None
    is_active: bool = Field(default=True)
