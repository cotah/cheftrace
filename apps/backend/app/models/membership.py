from uuid import UUID

from sqlmodel import Field, UniqueConstraint

from app.models.base import TimestampedBase


class RestaurantMembership(TimestampedBase, table=True):
    __tablename__ = "restaurant_memberships"
    __table_args__ = (UniqueConstraint("restaurant_id", "user_id"),)
    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    user_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    role: str = Field(nullable=False)
    is_active: bool = Field(default=True)
