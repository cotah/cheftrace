"""categories suppliers products

Revision ID: 002
Revises: 001
Create Date: 2026-05-06
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_categories",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
    )
    op.create_index(
        "ix_product_categories_restaurant",
        "product_categories",
        ["restaurant_id", "is_active"],
    )

    op.create_table(
        "suppliers",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("contact_name", sa.Text()),
        sa.Column("email", sa.Text()),
        sa.Column("phone", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
    )
    op.create_index(
        "ix_suppliers_restaurant",
        "suppliers",
        ["restaurant_id", "is_active"],
    )

    op.create_table(
        "products",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("product_categories.id"),
            nullable=True,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("sku", sa.Text()),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("unit_cost", sa.NUMERIC(12, 4)),
        sa.Column("minimum_stock_quantity", sa.NUMERIC(12, 3)),
        sa.Column(
            "expiry_required",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("storage_type", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
            "unit IN ('kg','g','l','ml','unit')",
            name="ck_products_unit",
        ),
    )
    op.create_index(
        "ix_products_restaurant",
        "products",
        ["restaurant_id", "is_active"],
    )
    op.create_index(
        "ix_products_category",
        "products",
        ["category_id"],
    )


def downgrade() -> None:
    op.drop_table("products")
    op.drop_table("suppliers")
    op.drop_table("product_categories")
