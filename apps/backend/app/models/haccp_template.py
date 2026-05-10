from uuid import UUID

from sqlmodel import Field

from app.models.base import TimestampedBase


class HACCPChecklistTemplate(TimestampedBase, table=True):
    __tablename__ = "haccp_checklist_templates"

    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    name: str = Field(nullable=False)
    frequency: str = Field(nullable=False)
    shifts_per_day: int | None = None
    is_equipment_dynamic: bool = Field(default=False, nullable=False)
    equipment_type_filter: str | None = None
    is_active: bool = Field(default=True)
    is_seed: bool = Field(default=False)
    created_by_user_id: UUID = Field(foreign_key="users.id", nullable=False)
