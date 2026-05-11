"""invoices

Revision ID: 008
Revises: 007
Create Date: 2026-05-11
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

INVOICE_STATUSES = "uploaded,processing,needs_review,confirmed,rejected"
LINE_ITEM_STATUSES = "suggested,confirmed,rejected"


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("suppliers.id"),
            nullable=True,
        ),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="uploaded"),
        sa.Column(
            "uploaded_by_user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("confirmed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("supplier_name_raw", sa.Text()),
        sa.Column("invoice_number", sa.Text()),
        sa.Column("invoice_date", sa.Date()),
        sa.Column("total_amount", sa.NUMERIC(12, 2)),
        sa.Column("vat_amount", sa.NUMERIC(12, 2)),
        sa.Column("raw_ocr_json", JSONB()),
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
            f"status IN ({','.join(repr(s) for s in INVOICE_STATUSES.split(','))})",
            name="ck_invoices_status",
        ),
    )
    op.create_index(
        "ix_invoices_restaurant",
        "invoices",
        ["restaurant_id", "status"],
    )
    op.create_index(
        "ix_invoices_uploaded_by",
        "invoices",
        ["uploaded_by_user_id"],
    )

    op.create_table(
        "invoice_line_items",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column(
            "invoice_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("invoices.id"),
            nullable=False,
        ),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text()),
        sa.Column(
            "suggested_product_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("products.id"),
            nullable=True,
        ),
        sa.Column(
            "confirmed_product_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("products.id"),
            nullable=True,
        ),
        sa.Column("quantity", sa.NUMERIC(12, 3)),
        sa.Column("unit", sa.Text()),
        sa.Column("unit_cost", sa.NUMERIC(12, 4)),
        sa.Column("total_cost", sa.NUMERIC(12, 2)),
        sa.Column("expiry_date", sa.Date()),
        sa.Column("batch_code", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default="suggested"),
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
            f"status IN ({','.join(repr(s) for s in LINE_ITEM_STATUSES.split(','))})",
            name="ck_invoice_line_items_status",
        ),
    )
    op.create_index(
        "ix_invoice_line_items_invoice",
        "invoice_line_items",
        ["invoice_id", "line_number"],
    )
    op.create_index(
        "ix_invoice_line_items_restaurant",
        "invoice_line_items",
        ["restaurant_id"],
    )


def downgrade() -> None:
    op.drop_table("invoice_line_items")
    op.drop_table("invoices")
