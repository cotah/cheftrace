from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.models.base import TimestampedBase
from app.models.enums import POSEventStatus


class PosEvent(TimestampedBase, table=True):
    """A raw webhook event from a POS provider, plus its processing state.

    Two reasons to record before processing:
    - Idempotency: (provider, external_event_id) is UNIQUE, so a webhook
      replay never causes a double-deduction.
    - Audit: the original payload survives even if we later decide to
      re-run processing with new mappings.
    """

    __tablename__ = "pos_events"
    # Mirror CHECK constraint from migration 012 so the pytest fixture
    # (SQLModel.metadata.create_all) enforces it like alembic does.
    __table_args__ = (
        sa.CheckConstraint(
            "processing_status IN ("
            "'pending','needs_mapping','pending_approval',"
            "'processed','insufficient_stock','failed','ignored'"
            ")",
            name="ck_pos_events_processing_status",
        ),
        sa.UniqueConstraint(
            "provider",
            "external_event_id",
            name="uq_pos_events_provider_external",
        ),
    )

    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    pos_integration_id: UUID = Field(
        foreign_key="pos_integrations.id",
        nullable=False,
        index=True,
    )
    provider: str = Field(nullable=False)
    external_event_id: str = Field(nullable=False)
    external_order_id: str | None = None
    event_type: str = Field(nullable=False)
    raw_payload: dict[str, Any] = Field(
        sa_column=sa.Column(JSONB, nullable=False),
    )
    received_at: datetime = Field(
        sa_column=sa.Column(
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    processing_status: str = Field(default=POSEventStatus.PENDING, nullable=False)
    processed_at: datetime | None = None
    error_message: str | None = None

    @property
    def processing_status_enum(self) -> POSEventStatus:
        return POSEventStatus(self.processing_status)
