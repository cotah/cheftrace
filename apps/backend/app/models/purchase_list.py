from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field

from app.models.base import TimestampedBase
from app.models.enums import PurchaseListStatus, PurchaseListType


class PurchaseList(TimestampedBase, table=True):
    __tablename__ = "purchase_lists"
    # Mirror CHECK constraints from migration 006 so the pytest fixture
    # (SQLModel.metadata.create_all) enforces them like alembic does.
    __table_args__ = (
        sa.CheckConstraint(
            "type IN ('food','beverage','non_food','mixed')",
            name="ck_purchase_lists_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft','sent','partially_received','received')",
            name="ck_purchase_lists_status",
        ),
    )

    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    type: str = Field(default=PurchaseListType.MIXED, nullable=False)
    status: str = Field(default=PurchaseListStatus.DRAFT, nullable=False)
    notes: str | None = None
    created_by_user_id: UUID = Field(foreign_key="users.id", nullable=False)
    sent_at: datetime | None = None
