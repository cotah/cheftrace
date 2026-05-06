"""users restaurants memberships

Revision ID: 001
Revises:
Create Date: 2026-05-06
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text()),
        sa.Column("preferred_lang", sa.Text(), nullable=False, server_default="pt-BR"),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "restaurants",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("legal_name", sa.Text()),
        sa.Column("address", sa.Text()),
        sa.Column("city", sa.Text()),
        sa.Column("country", sa.Text(), nullable=False, server_default="IE"),
        sa.Column("postal_code", sa.Text()),
        sa.Column("timezone", sa.Text(), nullable=False, server_default="Europe/Dublin"),
        sa.Column("currency", sa.Text(), nullable=False, server_default="EUR"),
        sa.Column("vat_number", sa.Text()),
        sa.Column("expiry_warning_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("critical_expiry_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("low_stock_alert_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("haccp_alert_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "restaurant_memberships",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id", PGUUID(as_uuid=True), sa.ForeignKey("restaurants.id"), nullable=False
        ),
        sa.Column("user_id", PGUUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("restaurant_id", "user_id", name="uq_memberships_restaurant_user"),
    )
    op.create_index("ix_memberships_user", "restaurant_memberships", ["user_id", "is_active"])
    op.create_index(
        "ix_memberships_restaurant", "restaurant_memberships", ["restaurant_id", "is_active"]
    )


def downgrade() -> None:
    op.drop_table("restaurant_memberships")
    op.drop_table("restaurants")
    op.drop_table("users")
