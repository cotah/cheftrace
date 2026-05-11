from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field

from app.models.base import TimestampedBase
from app.models.enums import POSConfirmationMode, POSProvider


class PosIntegration(TimestampedBase, table=True):
    """A restaurant's connection to one external POS provider.

    The `*_encrypted` columns hold pgp_sym_encrypt() output. The plaintext
    only ever lives in memory in the service layer; the model stores bytes
    and never knows the master key. See POSIntegrationService for the
    encrypt/decrypt entry points.
    """

    __tablename__ = "pos_integrations"
    # Mirror CHECK constraints from migration 012 so the pytest fixture
    # (SQLModel.metadata.create_all) enforces them like alembic does.
    __table_args__ = (
        sa.CheckConstraint(
            "provider IN ('square')",
            name="ck_pos_integrations_provider",
        ),
        sa.CheckConstraint(
            "confirmation_mode IN ('manual','auto')",
            name="ck_pos_integrations_confirmation_mode",
        ),
        sa.UniqueConstraint(
            "restaurant_id",
            "provider",
            name="uq_pos_integrations_restaurant_provider",
        ),
    )

    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    provider: str = Field(nullable=False)
    name: str = Field(nullable=False)
    access_token_encrypted: bytes | None = Field(
        default=None,
        sa_column=sa.Column(sa.LargeBinary(), nullable=True),
    )
    webhook_signing_key_encrypted: bytes | None = Field(
        default=None,
        sa_column=sa.Column(sa.LargeBinary(), nullable=True),
    )
    external_location_id: str | None = None
    confirmation_mode: str = Field(default=POSConfirmationMode.MANUAL, nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    last_sync_at: datetime | None = None
    created_by_user_id: UUID = Field(foreign_key="users.id", nullable=False)

    # Convenience accessors so callers don't have to import the StrEnum just
    # to test against string literals.
    @property
    def provider_enum(self) -> POSProvider:
        return POSProvider(self.provider)

    @property
    def confirmation_mode_enum(self) -> POSConfirmationMode:
        return POSConfirmationMode(self.confirmation_mode)
