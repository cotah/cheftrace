from pydantic import BaseModel


class ExpiryAlert(BaseModel):
    lot_id: str
    product_id: str
    product_name: str
    expiry_date: str
    days_left: int
    quantity_remaining: float
    unit: str


class LowStockAlert(BaseModel):
    product_id: str
    product_name: str
    quantity_remaining: float
    minimum_stock_quantity: float
    unit: str


class HACCPPendingAlert(BaseModel):
    template_id: str
    template_name: str
    frequency: str
    shift_number: int | None = None


class TemperatureAlert(BaseModel):
    log_id: str
    equipment_id: str
    equipment_name: str
    temperature: float
    min_temp: float | None = None
    max_temp: float | None = None
    recorded_at: str


class DashboardResponseChef(BaseModel):
    """Dashboard response for chef role — no financial data."""

    expiry_alerts: list[ExpiryAlert]
    critical_expiry: list[ExpiryAlert]
    low_stock: list[LowStockAlert]
    haccp_pending: list[HACCPPendingAlert]
    temperature_out_of_range: list[TemperatureAlert]
    total_active_lots: int


class DashboardResponseManager(DashboardResponseChef):
    """Dashboard response for manager/owner — includes financial data."""

    stock_value_eur: float | None = None
    stock_value_partial: bool = False
    lots_without_cost: int = 0
