from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from app.models.base import utcnow


class RecipeProduction(SQLModel, table=True):
    """Immutable audit row — one entry per confirmed `/produce/confirm`.

    No `updated_at`: a production is recorded once and never modified.
    To "cancel" a production the user creates manual_in stock movements
    to put the ingredients back (same pattern as stock_movements).
    """

    __tablename__ = "recipe_productions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    recipe_id: UUID = Field(foreign_key="recipes.id", nullable=False, index=True)
    batches: Decimal = Field(
        sa_column=sa.Column(sa.NUMERIC(12, 3), nullable=False),
    )
    produced_at: datetime = Field(default_factory=utcnow, nullable=False)
    produced_by_user_id: UUID = Field(foreign_key="users.id", nullable=False)
    notes: str | None = None
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
