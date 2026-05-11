"""pos_integrations + pos_events + pos_item_mappings + pgcrypto

Revision ID: 012
Revises: 011
Create Date: 2026-05-11

Phase 4 Part 1/4 foundation. Tables only — adapters, services, and
processing logic live in code. Tokens are stored encrypted via the
pgcrypto `pgp_sym_encrypt` family; the master key is read from the
POS_ENCRYPTION_KEY env var and never persisted in the DB.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None

# Single source of truth for the value lists. The models mirror these via
# __table_args__ so the pytest fixture (create_all) enforces the same CHECKs.
POS_PROVIDERS = "square"
CONFIRMATION_MODES = "manual,auto"
EVENT_STATUSES = (
    "pending,needs_mapping,pending_approval,processed,insufficient_stock,failed,ignored"
)


def upgrade() -> None:
    # pgcrypto exposes pgp_sym_encrypt / pgp_sym_decrypt used by the service
    # layer to round-trip POS access tokens. The extension is per-database
    # and idempotent, so CREATE IF NOT EXISTS is safe on re-runs.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "pos_integrations",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        # BYTEA columns hold pgp_sym_encrypt() output. NULL until the owner
        # finishes setup — the integration row may exist (so the UI can show
        # "needs credentials") before credentials are entered.
        sa.Column("access_token_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("webhook_signing_key_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("external_location_id", sa.Text(), nullable=True),
        sa.Column(
            "confirmation_mode",
            sa.Text(),
            nullable=False,
            server_default="manual",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_sync_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
            f"provider IN ({','.join(repr(p) for p in POS_PROVIDERS.split(','))})",
            name="ck_pos_integrations_provider",
        ),
        sa.CheckConstraint(
            f"confirmation_mode IN ({','.join(repr(m) for m in CONFIRMATION_MODES.split(','))})",
            name="ck_pos_integrations_confirmation_mode",
        ),
        # Keep it simple: one integration per (restaurant, provider) for MVP.
        # When we add multi-location support, drop this and add a separate
        # locations table.
        sa.UniqueConstraint(
            "restaurant_id",
            "provider",
            name="uq_pos_integrations_restaurant_provider",
        ),
    )
    op.create_index(
        "ix_pos_integrations_restaurant",
        "pos_integrations",
        ["restaurant_id", "is_active"],
    )

    op.create_table(
        "pos_events",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column(
            "pos_integration_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("pos_integrations.id"),
            nullable=False,
        ),
        # `provider` is denormalised so the idempotency UNIQUE works even if
        # an integration row gets deleted/recreated. The UNIQUE we actually
        # want is (provider, external_event_id) — that's the contract the
        # webhook providers offer.
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("external_event_id", sa.Text(), nullable=False),
        sa.Column("external_order_id", sa.Text(), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("raw_payload", JSONB, nullable=False),
        sa.Column(
            "received_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "processing_status",
            sa.Text(),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
            f"processing_status IN ({','.join(repr(s) for s in EVENT_STATUSES.split(','))})",
            name="ck_pos_events_processing_status",
        ),
        sa.UniqueConstraint(
            "provider",
            "external_event_id",
            name="uq_pos_events_provider_external",
        ),
    )
    op.create_index(
        "ix_pos_events_queue",
        "pos_events",
        ["restaurant_id", "processing_status", "received_at"],
    )
    op.create_index(
        "ix_pos_events_integration",
        "pos_events",
        ["pos_integration_id", "received_at"],
    )

    op.create_table(
        "pos_item_mappings",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column(
            "pos_integration_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("pos_integrations.id"),
            nullable=False,
        ),
        sa.Column("external_item_id", sa.Text(), nullable=False),
        sa.Column("external_item_name_snapshot", sa.Text(), nullable=False),
        # NULL recipe_id = "ignore this item, don't deduct anything". Lets
        # the owner suppress noise items (gift cards, service charges, etc.)
        # while keeping the mapping row for audit visibility.
        sa.Column(
            "recipe_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("recipes.id"),
            nullable=True,
        ),
        sa.Column(
            "units_per_sale",
            sa.NUMERIC(10, 3),
            nullable=False,
            server_default="1.000",
        ),
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
            "units_per_sale > 0",
            name="ck_pos_item_mappings_units_positive",
        ),
        sa.UniqueConstraint(
            "pos_integration_id",
            "external_item_id",
            name="uq_pos_item_mappings_integration_external",
        ),
    )
    op.create_index(
        "ix_pos_item_mappings_recipe",
        "pos_item_mappings",
        ["recipe_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_pos_item_mappings_recipe", table_name="pos_item_mappings")
    op.drop_table("pos_item_mappings")
    op.drop_index("ix_pos_events_integration", table_name="pos_events")
    op.drop_index("ix_pos_events_queue", table_name="pos_events")
    op.drop_table("pos_events")
    op.drop_index("ix_pos_integrations_restaurant", table_name="pos_integrations")
    op.drop_table("pos_integrations")
    # Intentionally NOT dropping the pgcrypto extension. Other parts of the
    # database may use it, and dropping it would break unrelated features.
