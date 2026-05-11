"""Pydantic schemas for recipes and recipe ingredients."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# Mirror the DB CHECK constraint on recipe_ingredients.unit.
IngredientUnit = Literal["kg", "g", "l", "ml", "unit"]


class RecipeIngredientCreate(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(gt=Decimal("0"))
    unit: IngredientUnit
    notes: str | None = None


class RecipeIngredientUpdate(BaseModel):
    quantity: Decimal | None = Field(default=None, gt=Decimal("0"))
    unit: IngredientUnit | None = None
    notes: str | None = None


class RecipeIngredientRead(BaseModel):
    id: UUID
    recipe_id: UUID
    product_id: UUID
    quantity: Decimal
    unit: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RecipeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    yield_quantity: Decimal = Field(gt=Decimal("0"))
    yield_unit: str = Field(min_length=1, max_length=50)
    prep_time_minutes: int | None = Field(default=None, ge=0)
    cook_time_minutes: int | None = Field(default=None, ge=0)
    instructions: str | None = None


class RecipeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    yield_quantity: Decimal | None = Field(default=None, gt=Decimal("0"))
    yield_unit: str | None = Field(default=None, min_length=1, max_length=50)
    prep_time_minutes: int | None = Field(default=None, ge=0)
    cook_time_minutes: int | None = Field(default=None, ge=0)
    instructions: str | None = None
    is_active: bool | None = None


class RecipeRead(BaseModel):
    id: UUID
    restaurant_id: UUID
    name: str
    yield_quantity: Decimal
    yield_unit: str
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    instructions: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RecipeWithIngredientsRead(RecipeRead):
    ingredients: list[RecipeIngredientRead] = []


# --- production preview / confirm --- #


class RecipeProductionPreviewRequest(BaseModel):
    batches: Decimal = Field(gt=Decimal("0"))


class RecipeProductionAllocation(BaseModel):
    """One slice of FEFO consumption from a single lot."""

    lot_id: UUID
    expiry_date: str | None = None  # ISO date — clients format it
    quantity_from_lot: Decimal
    unit_cost: Decimal | None = None
    unit: str


class RecipeProductionPreviewLine(BaseModel):
    """Per-ingredient outcome of producing N batches of this recipe."""

    ingredient_id: UUID
    product_id: UUID
    product_name: str
    ingredient_unit: str
    product_unit: str
    quantity_needed: Decimal
    available: Decimal
    shortage: bool
    unit_mismatch: bool
    allocations: list[RecipeProductionAllocation] = []


class RecipeProductionPreviewResponse(BaseModel):
    recipe_id: UUID
    batches: Decimal
    lines: list[RecipeProductionPreviewLine] = []
    can_confirm: bool


class RecipeProductionConfirmRequest(BaseModel):
    batches: Decimal = Field(gt=Decimal("0"))
    notes: str | None = None


class RecipeProductionRead(BaseModel):
    id: UUID
    restaurant_id: UUID
    recipe_id: UUID
    batches: Decimal
    produced_at: datetime
    produced_by_user_id: UUID
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
