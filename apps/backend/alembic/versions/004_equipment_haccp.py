"""equipment haccp tables

Revision ID: 004
Revises: 003
Create Date: 2026-05-06
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

EQUIPMENT_TYPES = "fridge,freezer,hot_hold,dry_store,display,prep_table,blast_chiller,other"
HACCP_FREQUENCIES = "daily,shift,on_delivery,weekly,monthly"
HACCP_ITEM_TYPES = "yes_no,temperature,numeric,text,multi_select,single_select"
HACCP_RUN_STATUSES = "pending,in_progress,completed,missed"


def upgrade() -> None:
    op.create_table(
        "equipment",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("equipment_type", sa.Text(), nullable=False),
        sa.Column("min_temp", sa.NUMERIC(5, 1)),
        sa.Column("max_temp", sa.NUMERIC(5, 1)),
        sa.Column("location", sa.Text()),
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
            f"equipment_type IN ({','.join(repr(t) for t in EQUIPMENT_TYPES.split(','))})",
            name="ck_equipment_type",
        ),
    )
    op.create_index("ix_equipment_restaurant", "equipment", ["restaurant_id", "is_active"])

    op.create_table(
        "temperature_logs",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column(
            "equipment_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("equipment.id"),
            nullable=False,
        ),
        sa.Column("temperature", sa.NUMERIC(5, 1), nullable=False),
        sa.Column(
            "is_out_of_range",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "recorded_by_user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("recorded_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_temperature_logs_restaurant",
        "temperature_logs",
        ["restaurant_id", "equipment_id"],
    )
    op.create_index(
        "ix_temperature_logs_recorded_at",
        "temperature_logs",
        ["restaurant_id", "recorded_at"],
    )

    op.create_table(
        "haccp_checklist_templates",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("frequency", sa.Text(), nullable=False),
        sa.Column("shifts_per_day", sa.Integer()),
        sa.Column(
            "is_equipment_dynamic",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_seed", sa.Boolean(), nullable=False, server_default="false"),
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
            f"frequency IN ({','.join(repr(f) for f in HACCP_FREQUENCIES.split(','))})",
            name="ck_haccp_template_frequency",
        ),
    )
    op.create_index(
        "ix_haccp_templates_restaurant",
        "haccp_checklist_templates",
        ["restaurant_id", "is_active"],
    )

    op.create_table(
        "haccp_checklist_item_templates",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column(
            "template_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("haccp_checklist_templates.id"),
            nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column(
            "equipment_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("equipment.id"),
            nullable=True,
        ),
        sa.Column("options_json", JSONB()),
        sa.Column("min_selections", sa.Integer()),
        sa.Column("max_selections", sa.Integer()),
        sa.Column(
            "is_required",
            sa.Boolean(),
            nullable=False,
            server_default="true",
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
            f"item_type IN ({','.join(repr(t) for t in HACCP_ITEM_TYPES.split(','))})",
            name="ck_haccp_item_type",
        ),
    )
    op.create_index(
        "ix_haccp_item_templates_template",
        "haccp_checklist_item_templates",
        ["template_id", "is_active"],
    )

    op.create_table(
        "haccp_checklist_runs",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column(
            "template_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("haccp_checklist_templates.id"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("shift_number", sa.Integer()),
        sa.Column("equipment_snapshot_json", JSONB()),
        sa.Column(
            "completed_by_user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True)),
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
            f"status IN ({','.join(repr(s) for s in HACCP_RUN_STATUSES.split(','))})",
            name="ck_haccp_run_status",
        ),
    )
    op.create_index(
        "ix_haccp_runs_restaurant_date",
        "haccp_checklist_runs",
        ["restaurant_id", "run_date", "status"],
    )

    op.create_table(
        "haccp_checklist_answers",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("haccp_checklist_runs.id"),
            nullable=False,
        ),
        sa.Column(
            "item_template_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("haccp_checklist_item_templates.id"),
            nullable=True,
        ),
        sa.Column(
            "equipment_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("equipment.id"),
            nullable=True,
        ),
        sa.Column("answer_bool", sa.Boolean()),
        sa.Column("answer_numeric", sa.NUMERIC(8, 2)),
        sa.Column("answer_text", sa.Text()),
        sa.Column("answer_options", JSONB()),
        sa.Column(
            "is_out_of_range",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("skip_reason", sa.Text()),
        sa.Column("skip_reason_text", sa.Text()),
        sa.Column(
            "answered_by_user_id",
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
            """
            NOT (
                skip_reason IS NOT NULL
                AND (
                    answer_bool IS NOT NULL
                    OR answer_numeric IS NOT NULL
                    OR answer_text IS NOT NULL
                    OR answer_options IS NOT NULL
                )
            )
            """,
            name="ck_haccp_answer_skip_xor",
        ),
    )
    op.create_index(
        "ix_haccp_answers_run",
        "haccp_checklist_answers",
        ["run_id"],
    )


def downgrade() -> None:
    op.drop_table("haccp_checklist_answers")
    op.drop_table("haccp_checklist_runs")
    op.drop_table("haccp_checklist_item_templates")
    op.drop_table("haccp_checklist_templates")
    op.drop_table("temperature_logs")
    op.drop_table("equipment")
