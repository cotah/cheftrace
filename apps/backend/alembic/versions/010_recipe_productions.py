"""recipe_productions + stock_movements.source_id

Revision ID: 010
Revises: 009
Create Date: 2026-05-11
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # New table: recipe_productions (immutable audit record).
    op.create_table(
        "recipe_productions",
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
        sa.Column("batches", sa.NUMERIC(12, 3), nullable=False),
        sa.Column(
            "produced_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "produced_by_user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "batches > 0",
            name="ck_recipe_productions_batches_positive",
        ),
    )
    op.create_index(
        "ix_recipe_productions_restaurant",
        "recipe_productions",
        ["restaurant_id", "produced_at"],
    )
    op.create_index(
        "ix_recipe_productions_recipe",
        "recipe_productions",
        ["recipe_id"],
    )

    # Add source_id to stock_movements so we can trace each consumption
    # back to the entity that caused it (recipe production today; future:
    # invoice id for OCR receipts, POS sale id for POS-driven consume).
    # Nullable + no FK so it can point at different tables polymorphically;
    # the source enum tells you which table to look in.
    op.add_column(
        "stock_movements",
        sa.Column("source_id", PGUUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_stock_movements_source",
        "stock_movements",
        ["source", "source_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_stock_movements_source", table_name="stock_movements")
    op.drop_column("stock_movements", "source_id")
    op.drop_table("recipe_productions")
