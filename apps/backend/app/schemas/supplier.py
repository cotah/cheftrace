from uuid import UUID

from pydantic import BaseModel


class SupplierCreate(BaseModel):
    name: str
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None


class SupplierRead(BaseModel):
    id: UUID
    name: str
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}
