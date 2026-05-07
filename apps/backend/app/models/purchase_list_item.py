from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field

from app.models.base import TimestampedBase
from app.models.enums import PurchaseListItemStatus


class PurchaseListItem(TimestampedBase, table=True):
    __tablename__ = "purchase_list_items"

    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    purchase_list_id: UUID = Field(foreign_key="purchase_lists.id", nullable=False, index=True)
    product_id: UUID = Field(foreign_key="products.id", nullable=False, index=True)
    supplier_id: UUID | None = Field(default=None, foreign_key="suppliers.id", nullable=True)
    quantity_ordered: Decimal = Field(sa_column=sa.Column(sa.NUMERIC(12, 3), nullable=False))
    quantity_received: Decimal | None = Field(
        default=None,
        sa_column=sa.Column(sa.NUMERIC(12, 3), nullable=True),
    )
    unit: str = Field(nullable=False)
    unit_cost_estimate: Decimal | None = Field(
        default=None,
        sa_column=sa.Column(sa.NUMERIC(12, 4), nullable=True),
    )
    status: str = Field(default=PurchaseListItemStatus.PENDING, nullable=False)
    notes: str | None = None
