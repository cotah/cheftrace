from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field

from app.models.base import TimestampedBase


class Recipe(TimestampedBase, table=True):
    __tablename__ = "recipes"

    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    name: str = Field(nullable=False)
    yield_quantity: Decimal = Field(
        sa_column=sa.Column(sa.NUMERIC(12, 3), nullable=False),
    )
    yield_unit: str = Field(nullable=False)
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    instructions: str | None = None
    is_active: bool = Field(default=True, nullable=False)
