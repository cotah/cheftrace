from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field

from app.models.base import TimestampedBase


class RecipeIngredient(TimestampedBase, table=True):
    __tablename__ = "recipe_ingredients"

    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    recipe_id: UUID = Field(foreign_key="recipes.id", nullable=False, index=True)
    product_id: UUID = Field(foreign_key="products.id", nullable=False, index=True)
    quantity: Decimal = Field(
        sa_column=sa.Column(sa.NUMERIC(12, 3), nullable=False),
    )
    unit: str = Field(nullable=False)
    notes: str | None = None
