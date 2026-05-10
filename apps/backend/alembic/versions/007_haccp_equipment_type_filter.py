"""haccp template equipment type filter

Revision ID: 007
Revises: 006
Create Date: 2026-05-11
"""

import sqlalchemy as sa

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "haccp_checklist_templates",
        sa.Column("equipment_type_filter", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("haccp_checklist_templates", "equipment_type_filter")
