from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator

EQUIPMENT_TYPES = (
    "fridge",
    "freezer",
    "hot_hold",
    "dry_store",
    "display",
    "prep_table",
    "blast_chiller",
    "other",
)

EQUIPMENT_DEFAULT_RANGES: dict[str, tuple[float, float] | None] = {
    "fridge": (0.0, 5.0),
    "freezer": (-25.0, -18.0),
    "hot_hold": (63.0, 90.0),
    "display": (0.0, 8.0),
    "prep_table": (0.0, 5.0),
    "blast_chiller": (-18.0, 5.0),
    "dry_store": None,
    "other": None,
}


class EquipmentCreate(BaseModel):
    name: str
    equipment_type: str
    min_temp: Decimal | None = None
    max_temp: Decimal | None = None
    location: str | None = None

    @model_validator(mode="after")
    def validate_equipment_type(self) -> "EquipmentCreate":
        if self.equipment_type not in EQUIPMENT_TYPES:
            raise ValueError(f"equipment_type must be one of: {', '.join(EQUIPMENT_TYPES)}")
        return self


class EquipmentRead(BaseModel):
    id: UUID
    name: str
    equipment_type: str
    min_temp: Decimal | None = None
    max_temp: Decimal | None = None
    location: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class TemperatureLogCreate(BaseModel):
    equipment_id: UUID
    temperature: Decimal
    notes: str | None = None
    recorded_at: str | None = None


class TemperatureLogRead(BaseModel):
    id: UUID
    equipment_id: UUID
    temperature: Decimal
    is_out_of_range: bool
    notes: str | None = None
    recorded_by_user_id: UUID
    recorded_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
