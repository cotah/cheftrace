from uuid import UUID

from pydantic import BaseModel


class RestaurantCreate(BaseModel):
    name: str
    legal_name: str | None = None
    address: str | None = None
    city: str | None = None
    country: str = "IE"
    postal_code: str | None = None
    timezone: str = "Europe/Dublin"
    currency: str = "EUR"
    vat_number: str | None = None


class RestaurantRead(BaseModel):
    id: UUID
    name: str
    legal_name: str | None = None
    city: str | None = None
    country: str
    timezone: str
    currency: str
    expiry_warning_days: int
    critical_expiry_days: int
    role: str | None = None  # current user's role in this restaurant; null if context unknown

    model_config = {"from_attributes": True}


class MemberRead(BaseModel):
    user_id: UUID
    email: str
    full_name: str | None = None
    role: str
    is_active: bool


class MemberInvite(BaseModel):
    email: str
    role: str


class MemberRoleUpdate(BaseModel):
    role: str
