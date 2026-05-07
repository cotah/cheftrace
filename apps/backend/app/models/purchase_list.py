from datetime import datetime
from uuid import UUID

from sqlmodel import Field

from app.models.base import TimestampedBase
from app.models.enums import PurchaseListStatus, PurchaseListType


class PurchaseList(TimestampedBase, table=True):
    __tablename__ = "purchase_lists"

    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    type: str = Field(default=PurchaseListType.MIXED, nullable=False)
    status: str = Field(default=PurchaseListStatus.DRAFT, nullable=False)
    notes: str | None = None
    created_by_user_id: UUID = Field(foreign_key="users.id", nullable=False)
    sent_at: datetime | None = None
