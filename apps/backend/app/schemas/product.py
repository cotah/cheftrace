from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import UnitKind


class ProductCreate(BaseModel):
    name: str
    sku: str | None = None
    unit: UnitKind
    category_id: UUID | None = None
    unit_cost: Decimal | None = None
    minimum_stock_quantity: Decimal | None = None
    expiry_required: bool = False
    storage_type: str | None = None


class ProductRead(BaseModel):
    id: UUID
    name: str
    sku: str | None = None
    unit: str
    category_id: UUID | None = None
    expiry_required: bool
    storage_type: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class ProductReadWithCost(ProductRead):
    """Extended read for manager/owner — includes cost fields."""

    unit_cost: Decimal | None = None
    minimum_stock_quantity: Decimal | None = None
