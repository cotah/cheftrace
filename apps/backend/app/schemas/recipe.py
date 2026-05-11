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
