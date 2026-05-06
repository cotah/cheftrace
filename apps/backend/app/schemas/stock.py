from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.models.enums import ExpiryReason, UnitKind


class LotCreate(BaseModel):
    product_id: UUID
    supplier_id: UUID | None = None
    quantity_received: Decimal
    unit: UnitKind
    unit_cost: Decimal | None = None
    expiry_date: date | None = None
    received_date: date | None = None
    notes: str | None = None


class LotExpiryUpdate(BaseModel):
    expiry_date: date
    reason: ExpiryReason

    @field_validator("reason")
    @classmethod
    def reason_required(cls, v: ExpiryReason) -> ExpiryReason:
        return v


class LotRead(BaseModel):
    id: UUID
    product_id: UUID
    supplier_id: UUID | None = None
    quantity_received: Decimal
    quantity_remaining: Decimal
    unit: str
    expiry_date: date | None = None
    received_date: date
    status: str
    notes: str | None = None
    created_by_user_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class LotReadWithCost(LotRead):
    """Extended read for manager/owner."""

    unit_cost: Decimal | None = None


class ManualInInput(BaseModel):
    product_id: UUID
    lot_id: UUID
    quantity: Decimal
    unit: UnitKind
    reason: str | None = None
    notes: str | None = None


class ManualOutInput(BaseModel):
    product_id: UUID
    lot_id: UUID | None = None
    quantity: Decimal
    unit: UnitKind
    reason: str | None = None
    notes: str | None = None


class AdjustmentInput(BaseModel):
    product_id: UUID
    lot_id: UUID | None = None
    quantity: Decimal
    unit: UnitKind
    reason: str
    notes: str | None = None


class MovementRead(BaseModel):
    id: UUID
    product_id: UUID
    lot_id: UUID | None = None
    kind: str
    source: str
    quantity: Decimal
    unit: str
    reason: str | None = None
    notes: str | None = None
    created_by_user_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogRead(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    action: str
    reason: str | None = None
    before_value: dict[str, Any] | None = None
    after_value: dict[str, Any] | None = None
    changed_by_user_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
