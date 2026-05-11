"""Pydantic schemas for POS integrations.

Read schemas never leak ciphertext or plaintext credentials — only
boolean `has_*` flags so the UI can show "credentials configured" vs
"needs setup". Setting credentials uses a dedicated request schema so
secrets are never mixed with regular CRUD payloads.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.pos_event import PosEvent
from app.models.pos_integration import PosIntegration
from app.models.pos_item_mapping import PosItemMapping


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


class POSEventRead(BaseModel):
    """Compact view of a POS event for the queue list."""

    id: UUID
    pos_integration_id: UUID
    provider: str
    external_event_id: str
    external_order_id: str | None = None
    event_type: str
    processing_status: str
    processed_at: datetime | None = None
    error_message: str | None = None
    received_at: datetime
    created_at: datetime

    @classmethod
    def from_model(cls, m: PosEvent) -> "POSEventRead":
        return cls(
            id=m.id,
            pos_integration_id=m.pos_integration_id,
            provider=m.provider,
            external_event_id=m.external_event_id,
            external_order_id=m.external_order_id,
            event_type=m.event_type,
            processing_status=m.processing_status,
            processed_at=m.processed_at,
            error_message=m.error_message,
            received_at=m.received_at,
            created_at=m.created_at,
        )


class POSEventDetail(POSEventRead):
    """Detail view — includes the raw payload for debugging."""

    raw_payload: dict[str, Any]

    @classmethod
    def from_model(cls, m: PosEvent) -> "POSEventDetail":
        base = POSEventRead.from_model(m)
        return cls(**base.model_dump(), raw_payload=m.raw_payload)


class POSEventDismissRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class POSEventProcessResponse(BaseModel):
    """What the process / dismiss endpoints return.

    Mirrors ProcessingResult from the service so the UI can render a
    short outcome string without having to interpret status alone.
    """

    status: str
    movements_created: int = 0
    error_message: str | None = None
    unmapped_item_ids: list[str] = []
    insufficient_product_ids: list[UUID] = []


# --- item mappings --- #


class POSItemMappingCreate(BaseModel):
    external_item_id: str = Field(min_length=1, max_length=200)
    external_item_name_snapshot: str = Field(min_length=1, max_length=200)
    # `recipe_id is None` is an explicit "ignore this item" mapping.
    # Different from "no mapping" (NEEDS_MAPPING) — see service comments.
    recipe_id: UUID | None = None
    units_per_sale: Decimal = Field(default=Decimal("1.000"), gt=Decimal("0"))


class POSItemMappingUpdate(BaseModel):
    """Partial update.

    The endpoint extracts fields via model_dump(exclude_unset=True) to
    distinguish "field absent in request" from "field explicitly set
    to None". The latter is meaningful for recipe_id (= flip to ignore).
    """

    external_item_name_snapshot: str | None = Field(default=None, min_length=1, max_length=200)
    recipe_id: UUID | None = None
    units_per_sale: Decimal | None = Field(default=None, gt=Decimal("0"))
    is_active: bool | None = None


class POSItemMappingRead(BaseModel):
    id: UUID
    pos_integration_id: UUID
    external_item_id: str
    external_item_name_snapshot: str
    recipe_id: UUID | None = None
    units_per_sale: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, m: PosItemMapping) -> "POSItemMappingRead":
        return cls(
            id=m.id,
            pos_integration_id=m.pos_integration_id,
            external_item_id=m.external_item_id,
            external_item_name_snapshot=m.external_item_name_snapshot,
            recipe_id=m.recipe_id,
            units_per_sale=m.units_per_sale,
            is_active=m.is_active,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
