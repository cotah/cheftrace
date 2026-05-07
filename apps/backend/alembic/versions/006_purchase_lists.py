"""purchase lists

Revision ID: 006
Revises: 005
Create Date: 2026-05-07
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

LIST_TYPES = "food,beverage,non_food,mixed"
LIST_STATUSES = "draft,sent,partially_received,received"
ITEM_STATUSES = "pending,received,partial,not_received"
UNIT_KINDS = "kg,g,l,ml,unit"


def upgrade() -> None:
    op.create_table(
        "purchase_lists",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column("type", sa.Text(), nullable=False, server_default="mixed"),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "created_by_user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True)),
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
            f"type IN ({','.join(repr(t) for t in LIST_TYPES.split(','))})",
            name="ck_purchase_lists_type",
        ),
        sa.CheckConstraint(
            f"status IN ({','.join(repr(s) for s in LIST_STATUSES.split(','))})",
            name="ck_purchase_lists_status",
        ),
    )
    op.create_index(
        "ix_purchase_lists_restaurant",
        "purchase_lists",
        ["restaurant_id", "status"],
    )

    op.create_table(
        "purchase_list_items",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column(
            "purchase_list_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("purchase_lists.id"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("products.id"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("suppliers.id"),
            nullable=True,
        ),
        sa.Column("quantity_ordered", sa.NUMERIC(12, 3), nullable=False),
        sa.Column("quantity_received", sa.NUMERIC(12, 3)),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("unit_cost_estimate", sa.NUMERIC(12, 4)),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
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
            f"status IN ({','.join(repr(s) for s in ITEM_STATUSES.split(','))})",
            name="ck_purchase_list_items_status",
        ),
        sa.CheckConstraint(
            f"unit IN ({','.join(repr(u) for u in UNIT_KINDS.split(','))})",
            name="ck_purchase_list_items_unit",
        ),
        sa.CheckConstraint(
            "quantity_ordered > 0",
            name="ck_purchase_list_items_quantity_positive",
        ),
    )
    op.create_index(
        "ix_purchase_list_items_list",
        "purchase_list_items",
        ["purchase_list_id", "status"],
    )
    op.create_index(
        "ix_purchase_list_items_restaurant",
        "purchase_list_items",
        ["restaurant_id"],
    )


def downgrade() -> None:
    op.drop_table("purchase_list_items")
    op.drop_table("purchase_lists")
