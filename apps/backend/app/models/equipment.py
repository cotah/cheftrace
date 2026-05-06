from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field

from app.models.base import TimestampedBase


class Equipment(TimestampedBase, table=True):
    __tablename__ = "equipment"

    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    name: str = Field(nullable=False)
    equipment_type: str = Field(nullable=False)
    min_temp: Decimal | None = Field(
        default=None,
        sa_column=sa.Column(sa.NUMERIC(5, 1), nullable=True),
    )
    max_temp: Decimal | None = Field(
        default=None,
        sa_column=sa.Column(sa.NUMERIC(5, 1), nullable=True),
    )
    location: str | None = None
    is_active: bool = Field(default=True)
