from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field

from app.models.base import TimestampedBase


class HACCPChecklistItemTemplate(TimestampedBase, table=True):
    __tablename__ = "haccp_checklist_item_templates"

    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    template_id: UUID = Field(
        foreign_key="haccp_checklist_templates.id",
        nullable=False,
        index=True,
    )
    order_index: int = Field(nullable=False)
    question: str = Field(nullable=False)
    item_type: str = Field(nullable=False)
    equipment_id: UUID | None = Field(default=None, foreign_key="equipment.id", nullable=True)
    options_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=sa.Column(sa.JSON, nullable=True),
    )
    min_selections: int | None = None
    max_selections: int | None = None
    is_required: bool = Field(default=True)
    is_active: bool = Field(default=True)
