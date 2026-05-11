"""extend stock_movements.source CHECK to include 'recipe'

Revision ID: 011
Revises: 010
Create Date: 2026-05-11

Production hotfix. Phase 3 Part 2/3 added MovementSource.RECIPE and
started writing stock_movements rows with source='recipe' on every
recipe production. The CHECK constraint from migration 003 was never
updated to include 'recipe', so every /produce/confirm in production
fails with CheckViolationError and returns 500.

Postgres has no ALTER CHECK CONSTRAINT, so the constraint is rewritten
via DROP + ADD. No data backfill needed: the old constraint was
already rejecting every 'recipe' insert, so no surviving rows have
that value.

Note on the test gap: the pytest fixture builds tables via
SQLModel.metadata.create_all instead of running migrations, so the
CHECK was never enforced in tests. Out of scope for this hotfix.
"""

from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_stock_movements_source",
        "stock_movements",
        type_="check",
    )
    op.create_check_constraint(
        "ck_stock_movements_source",
        "stock_movements",
        "source IN ('manual','purchase_list','pos','ocr','recipe')",
    )


def downgrade() -> None:
    # Will fail with CheckViolationError if rows with source='recipe'
    # exist at downgrade time — that's correct, since those rows would
    # violate the older constraint. Clean them up before downgrading.
    op.drop_constraint(
        "ck_stock_movements_source",
        "stock_movements",
        type_="check",
    )
    op.create_check_constraint(
        "ck_stock_movements_source",
        "stock_movements",
        "source IN ('manual','purchase_list','pos','ocr')",
    )
