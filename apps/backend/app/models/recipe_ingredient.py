from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field

from app.models.base import TimestampedBase


class RecipeIngredient(TimestampedBase, table=True):
    __tablename__ = "recipe_ingredients"
    # Mirror CHECK constraints from migration 009 so the pytest fixture
    # (SQLModel.metadata.create_all) enforces them like alembic does.
    __table_args__ = (
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_recipe_ingredients_quantity_positive",
        ),
        sa.CheckConstraint(
            "unit IN ('kg','g','l','ml','unit')",
            name="ck_recipe_ingredients_unit",
        ),
    )

    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    recipe_id: UUID = Field(foreign_key="recipes.id", nullable=False, index=True)
    product_id: UUID = Field(foreign_key="products.id", nullable=False, index=True)
    quantity: Decimal = Field(
        sa_column=sa.Column(sa.NUMERIC(12, 3), nullable=False),
    )
    unit: str = Field(nullable=False)
    notes: str | None = None
