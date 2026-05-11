from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field

from app.models.base import TimestampedBase


class PosItemMapping(TimestampedBase, table=True):
    """Links a POS provider's menu item to a ChefTrace recipe.

    `recipe_id IS NULL` is an intentional "ignore" state — the owner has
    seen the item and decided that a sale of it should not move stock
    (e.g. gift cards, service charges). Keeping the row preserves audit
    visibility instead of silently dropping unmapped sales.

    `units_per_sale` is how many portions of the recipe a single POS sale
    represents. Default 1.000 covers "one menu item = one portion". A
    combo deal that yields half a portion of a recipe would use 0.500.
    """

    __tablename__ = "pos_item_mappings"
    # Mirror CHECK constraints from migration 012 so the pytest fixture
    # (SQLModel.metadata.create_all) enforces them like alembic does.
    __table_args__ = (
        sa.CheckConstraint(
            "units_per_sale > 0",
            name="ck_pos_item_mappings_units_positive",
        ),
        sa.UniqueConstraint(
            "pos_integration_id",
            "external_item_id",
            name="uq_pos_item_mappings_integration_external",
        ),
    )

    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    pos_integration_id: UUID = Field(
        foreign_key="pos_integrations.id",
        nullable=False,
        index=True,
    )
    external_item_id: str = Field(nullable=False)
    external_item_name_snapshot: str = Field(nullable=False)
    recipe_id: UUID | None = Field(
        default=None,
        foreign_key="recipes.id",
        nullable=True,
    )
    units_per_sale: Decimal = Field(
        default=Decimal("1.000"),
        sa_column=sa.Column(sa.NUMERIC(10, 3), nullable=False, server_default="1.000"),
    )
    is_active: bool = Field(default=True, nullable=False)
