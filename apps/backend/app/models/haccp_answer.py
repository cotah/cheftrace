from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from app.models.base import utcnow


class HACCPChecklistAnswer(SQLModel, table=True):
    __tablename__ = "haccp_checklist_answers"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    run_id: UUID = Field(foreign_key="haccp_checklist_runs.id", nullable=False, index=True)
    item_template_id: UUID | None = Field(
        default=None,
        foreign_key="haccp_checklist_item_templates.id",
        nullable=True,
    )
    equipment_id: UUID | None = Field(default=None, foreign_key="equipment.id", nullable=True)
    answer_bool: bool | None = None
    answer_numeric: Decimal | None = Field(
        default=None,
        sa_column=sa.Column(sa.NUMERIC(8, 2), nullable=True),
    )
    answer_text: str | None = None
    answer_options: list[str] | None = Field(
        default=None,
        sa_column=sa.Column(sa.JSON, nullable=True),
    )
    is_out_of_range: bool = Field(default=False, nullable=False)
    skip_reason: str | None = None
    skip_reason_text: str | None = None
    answered_by_user_id: UUID = Field(foreign_key="users.id", nullable=False)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
