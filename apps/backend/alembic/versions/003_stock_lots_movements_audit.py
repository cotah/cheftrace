"""stock lots movements audit

Revision ID: 003
Revises: 002
Create Date: 2026-05-06
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_lots",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
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
        sa.Column("quantity_received", sa.NUMERIC(12, 3), nullable=False),
        sa.Column("quantity_remaining", sa.NUMERIC(12, 3), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("unit_cost", sa.NUMERIC(12, 4)),
        sa.Column("expiry_date", sa.Date()),
        sa.Column(
            "received_date",
            sa.Date(),
            nullable=False,
            server_default=sa.func.current_date(),
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="active",
        ),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "created_by_user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
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
            "quantity_remaining >= 0",
            name="ck_stock_lots_quantity_remaining_non_negative",
        ),
        sa.CheckConstraint(
            "status IN ('active','depleted','expired','discarded')",
            name="ck_stock_lots_status",
        ),
        sa.CheckConstraint(
            "unit IN ('kg','g','l','ml','unit')",
            name="ck_stock_lots_unit",
        ),
    )
    op.create_index(
        "ix_stock_lots_restaurant_product",
        "stock_lots",
        ["restaurant_id", "product_id", "status"],
    )
    op.create_index(
        "ix_stock_lots_expiry",
        "stock_lots",
        ["restaurant_id", "expiry_date"],
    )

    op.create_table(
        "stock_movements",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("products.id"),
            nullable=False,
        ),
        sa.Column(
            "lot_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("stock_lots.id"),
            nullable=True,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False, server_default="manual"),
        sa.Column("quantity", sa.NUMERIC(12, 3), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "created_by_user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "kind IN ('receive','manual_in','manual_out','adjustment','discard','consume')",
            name="ck_stock_movements_kind",
        ),
        sa.CheckConstraint(
            "source IN ('manual','purchase_list','pos','ocr')",
            name="ck_stock_movements_source",
        ),
        sa.CheckConstraint(
            "unit IN ('kg','g','l','ml','unit')",
            name="ck_stock_movements_unit",
        ),
    )
    op.create_index(
        "ix_stock_movements_restaurant_product",
        "stock_movements",
        ["restaurant_id", "product_id"],
    )
    op.create_index(
        "ix_stock_movements_lot",
        "stock_movements",
        ["lot_id"],
    )

    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_stock_movement_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'stock_movements are immutable: use a compensating movement instead';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_stock_movements_immutable
        BEFORE UPDATE OR DELETE ON stock_movements
        FOR EACH ROW EXECUTE FUNCTION prevent_stock_movement_mutation();
    """)

    op.create_table(
        "audit_logs",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("before_value", sa.JSON()),
        sa.Column("after_value", sa.JSON()),
        sa.Column(
            "changed_by_user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_audit_logs_restaurant",
        "audit_logs",
        ["restaurant_id", "entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.execute("DROP TRIGGER IF EXISTS trg_stock_movements_immutable ON stock_movements;")
    op.execute("DROP FUNCTION IF EXISTS prevent_stock_movement_mutation();")
    op.drop_table("stock_movements")
    op.drop_table("stock_lots")
