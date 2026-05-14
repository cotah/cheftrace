"""haccp templates frequency fix — monthly for periodic records

Revision ID: 013
Revises: 012
Create Date: 2026-05-14

Four seed templates were originally created with frequency='on_delivery',
which caused them to surface on the dashboard daily. They are actually
periodic / event-driven records that belong on a monthly cadence:

  - Allergen Record
  - Accident and Incident Record
  - SC6 — Staff Hygiene Training Record
  - SC7 — Fitness to Work Assessment

This is a pure data migration — no schema changes. The UPDATE is
idempotent (matching by name in restaurant-scoped rows): re-running
the migration on already-corrected rows is a no-op.

Restaurants whose templates were customised under a different name will
not be touched. Restaurants that never received these templates (e.g.
created before they were seeded) get them via the in-app reseed flow.
"""

from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE haccp_checklist_templates
        SET frequency = 'monthly'
        WHERE name IN (
            'Allergen Record',
            'Accident and Incident Record',
            'SC6 — Staff Hygiene Training Record',
            'SC7 — Fitness to Work Assessment'
        )
          AND frequency = 'on_delivery'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE haccp_checklist_templates
        SET frequency = 'on_delivery'
        WHERE name IN (
            'Allergen Record',
            'Accident and Incident Record',
            'SC6 — Staff Hygiene Training Record',
            'SC7 — Fitness to Work Assessment'
        )
          AND frequency = 'monthly'
        """
    )
