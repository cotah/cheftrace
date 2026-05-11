"""recipes + recipe_ingredients

Revision ID: 009
Revises: 008
Create Date: 2026-05-11
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None

# Ingredient unit must come from the standard set so reports and FEFO
# stay coherent. yield_unit on the recipe stays free-form ("portion",
# "batch", "L", "kg", etc.) because product-level concepts don't apply
# there.
UNIT_KINDS = "kg,g,l,ml,unit"


def upgrade() -> None:
    op.create_table(
        "recipes",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("yield_quantity", sa.NUMERIC(12, 3), nullable=False),
        sa.Column("yield_unit", sa.Text(), nullable=False),
        sa.Column("prep_time_minutes", sa.Integer()),
        sa.Column("cook_time_minutes", sa.Integer()),
        sa.Column("instructions", sa.Text()),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "yield_quantity > 0",
            name="ck_recipes_yield_positive",
        ),
    )
    op.create_index(
        "ix_recipes_restaurant",
        "recipes",
        ["restaurant_id", "is_active"],
    )

    op.create_table(
        "recipe_ingredients",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column(
            "recipe_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("recipes.id"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("products.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.NUMERIC(12, 3), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_recipe_ingredients_quantity_positive",
        ),
        sa.CheckConstraint(
            f"unit IN ({','.join(repr(u) for u in UNIT_KINDS.split(','))})",
            name="ck_recipe_ingredients_unit",
        ),
    )
    op.create_index(
        "ix_recipe_ingredients_recipe",
        "recipe_ingredients",
        ["recipe_id"],
    )
    op.create_index(
        "ix_recipe_ingredients_restaurant",
        "recipe_ingredients",
        ["restaurant_id"],
    )
    op.create_index(
        "ix_recipe_ingredients_product",
        "recipe_ingredients",
        ["product_id"],
    )


def downgrade() -> None:
    op.drop_table("recipe_ingredients")
    op.drop_table("recipes")
