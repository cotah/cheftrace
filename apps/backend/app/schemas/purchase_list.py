from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import PurchaseListType, UnitKind


class PurchaseListCreate(BaseModel):
    type: PurchaseListType = PurchaseListType.MIXED
    notes: str | None = None


class PurchaseListUpdate(BaseModel):
    type: PurchaseListType | None = None
    notes: str | None = None


class PurchaseListItemCreate(BaseModel):
    product_id: UUID
    supplier_id: UUID | None = None
    quantity_ordered: Decimal
    unit: UnitKind
    unit_cost_estimate: Decimal | None = None
    notes: str | None = None


class PurchaseListItemUpdate(BaseModel):
    quantity_ordered: Decimal | None = None
    unit_cost_estimate: Decimal | None = None
    supplier_id: UUID | None = None
    notes: str | None = None


class PurchaseListItemRead(BaseModel):
    id: UUID
    purchase_list_id: UUID
    product_id: UUID
    supplier_id: UUID | None = None
    quantity_ordered: Decimal
    quantity_received: Decimal | None = None
    unit: str
    unit_cost_estimate: Decimal | None = None
    status: str
    notes: str | None = None

    model_config = {"from_attributes": True}


class PurchaseListRead(BaseModel):
    id: UUID
    type: str
    status: str
    notes: str | None = None
    created_by_user_id: UUID
    sent_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PurchaseListWithItemsRead(PurchaseListRead):
    items: list[PurchaseListItemRead] = []


class ReceiveItemInput(BaseModel):
    quantity_received: Decimal
    expiry_date: date | None = None
    unit_cost: Decimal | None = None
    notes: str | None = None
