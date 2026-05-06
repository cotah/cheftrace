from uuid import UUID

from sqlmodel import Field

from app.models.base import TimestampedBase


class ProductCategory(TimestampedBase, table=True):
    __tablename__ = "product_categories"

    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    name: str = Field(nullable=False)
    is_active: bool = Field(default=True)
