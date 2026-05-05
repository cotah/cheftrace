"""Base model definitions for SQLModel entities."""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class TimestampMixin(SQLModel):
    """Mixin adding created_at and updated_at columns."""

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
