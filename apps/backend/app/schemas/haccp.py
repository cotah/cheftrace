from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class HACCPTemplateCreate(BaseModel):
    name: str
    frequency: str
    shifts_per_day: int | None = None
    is_equipment_dynamic: bool = False


class HACCPTemplateRead(BaseModel):
    id: UUID
    name: str
    frequency: str
    shifts_per_day: int | None = None
    is_equipment_dynamic: bool
    is_active: bool
    is_seed: bool

    model_config = {"from_attributes": True}


class HACCPItemCreate(BaseModel):
    question: str
    item_type: str
    order_index: int
    equipment_id: UUID | None = None
    options_json: dict[str, Any] | None = None
    min_selections: int | None = None
    max_selections: int | None = None
    is_required: bool = True


class HACCPItemRead(BaseModel):
    id: UUID
    template_id: UUID
    order_index: int
    question: str
    item_type: str
    equipment_id: UUID | None = None
    options_json: dict[str, Any] | None = None
    min_selections: int | None = None
    max_selections: int | None = None
    is_required: bool
    is_active: bool

    model_config = {"from_attributes": True}


class HACCPRunCreate(BaseModel):
    template_id: UUID
    run_date: date
    shift_number: int | None = None
    notes: str | None = None


class HACCPRunRead(BaseModel):
    id: UUID
    template_id: UUID
    status: str
    run_date: str
    shift_number: int | None = None
    completed_by_user_id: UUID | None = None
    completed_at: str | None = None
    notes: str | None = None
    created_by_user_id: UUID

    model_config = {"from_attributes": True}


SKIP_REASONS = (
    "equipment_in_defrost",
    "under_maintenance",
    "equipment_newly_added",
    "equipment_temporarily_offline",
    "other",
)


class HACCPAnswerCreate(BaseModel):
    item_template_id: UUID | None = None
    equipment_id: UUID | None = None
    answer_bool: bool | None = None
    answer_numeric: float | None = None
    answer_text: str | None = None
    answer_options: list[str] | None = None
    skip_reason: str | None = None
    skip_reason_text: str | None = None


class HACCPAnswerRead(BaseModel):
    id: UUID
    run_id: UUID
    item_template_id: UUID | None = None
    equipment_id: UUID | None = None
    answer_bool: bool | None = None
    answer_numeric: float | None = None
    answer_text: str | None = None
    answer_options: list[str] | None = None
    is_out_of_range: bool
    skip_reason: str | None = None
    skip_reason_text: str | None = None
    answered_by_user_id: UUID

    model_config = {"from_attributes": True}
