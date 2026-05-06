from datetime import date, datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field

from app.models.base import TimestampedBase


class HACCPChecklistRun(TimestampedBase, table=True):
    __tablename__ = "haccp_checklist_runs"

    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    template_id: UUID = Field(
        foreign_key="haccp_checklist_templates.id",
        nullable=False,
        index=True,
    )
    status: str = Field(default="pending", nullable=False)
    run_date: date = Field(nullable=False, index=True)
    shift_number: int | None = None
    equipment_snapshot_json: list[dict[str, Any]] | None = Field(
        default=None,
        sa_column=sa.Column(sa.JSON, nullable=True),
    )
    completed_by_user_id: UUID | None = Field(default=None, foreign_key="users.id", nullable=True)
    completed_at: datetime | None = None
    notes: str | None = None
    created_by_user_id: UUID = Field(foreign_key="users.id", nullable=False)
