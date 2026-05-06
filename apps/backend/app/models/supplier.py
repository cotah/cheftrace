from uuid import UUID

from sqlmodel import Field

from app.models.base import TimestampedBase


class Supplier(TimestampedBase, table=True):
    __tablename__ = "suppliers"

    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    name: str = Field(nullable=False)
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None
    is_active: bool = Field(default=True)
