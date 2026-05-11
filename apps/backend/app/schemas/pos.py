"""Pydantic schemas for POS integrations.

Read schemas never leak ciphertext or plaintext credentials — only
boolean `has_*` flags so the UI can show "credentials configured" vs
"needs setup". Setting credentials uses a dedicated request schema so
secrets are never mixed with regular CRUD payloads.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.pos_integration import PosIntegration


class POSIntegrationCreate(BaseModel):
    provider: Literal["square"]
    name: str = Field(min_length=1, max_length=200)
    external_location_id: str | None = Field(default=None, max_length=200)


class POSIntegrationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    external_location_id: str | None = Field(default=None, max_length=200)
    confirmation_mode: Literal["manual", "auto"] | None = None
    is_active: bool | None = None


class POSIntegrationSetCredentials(BaseModel):
    access_token: str = Field(min_length=1, max_length=4096)
    webhook_signing_key: str = Field(min_length=1, max_length=4096)

    @field_validator("access_token", "webhook_signing_key")
    @classmethod
    def reject_whitespace_only(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank or whitespace-only")
        return value


class POSIntegrationRead(BaseModel):
    id: UUID
    restaurant_id: UUID
    provider: str
    name: str
    external_location_id: str | None = None
    confirmation_mode: str
    is_active: bool
    last_sync_at: datetime | None = None
    has_access_token: bool
    has_webhook_signing_key: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, m: PosIntegration) -> "POSIntegrationRead":
        return cls(
            id=m.id,
            restaurant_id=m.restaurant_id,
            provider=m.provider,
            name=m.name,
            external_location_id=m.external_location_id,
            confirmation_mode=m.confirmation_mode,
            is_active=m.is_active,
            last_sync_at=m.last_sync_at,
            has_access_token=m.access_token_encrypted is not None,
            has_webhook_signing_key=m.webhook_signing_key_encrypted is not None,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
