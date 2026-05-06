from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from app.models.base import utcnow


class TemperatureLog(SQLModel, table=True):
    __tablename__ = "temperature_logs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    equipment_id: UUID = Field(foreign_key="equipment.id", nullable=False, index=True)
    temperature: Decimal = Field(sa_column=sa.Column(sa.NUMERIC(5, 1), nullable=False))
    is_out_of_range: bool = Field(default=False, nullable=False)
    notes: str | None = None
    recorded_by_user_id: UUID = Field(foreign_key="users.id", nullable=False)
    recorded_at: datetime = Field(nullable=False)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
