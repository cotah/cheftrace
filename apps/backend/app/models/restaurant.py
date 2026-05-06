from sqlmodel import Field

from app.models.base import TimestampedBase


class Restaurant(TimestampedBase, table=True):
    __tablename__ = "restaurants"
    name: str = Field(nullable=False)
    legal_name: str | None = None
    address: str | None = None
    city: str | None = None
    country: str = Field(default="IE")
    postal_code: str | None = None
    timezone: str = Field(default="Europe/Dublin")
    currency: str = Field(default="EUR")
    vat_number: str | None = None
    expiry_warning_days: int = Field(default=3)
    critical_expiry_days: int = Field(default=1)
    low_stock_alert_enabled: bool = Field(default=True)
    haccp_alert_enabled: bool = Field(default=True)
    is_active: bool = Field(default=True)
