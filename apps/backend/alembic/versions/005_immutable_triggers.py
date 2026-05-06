"""immutable triggers for temperature_logs, haccp_checklist_answers, audit_logs

Revision ID: 005
Revises: 004
Create Date: 2026-05-06
"""

from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_immutable_record_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'Records in % are immutable. Create a correction record instead.',
                TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
    """)

    for table in ("temperature_logs", "haccp_checklist_answers", "audit_logs"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_immutable
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION prevent_immutable_record_modification();
        """)


def downgrade() -> None:
    for table in ("temperature_logs", "haccp_checklist_answers", "audit_logs"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable ON {table};")
    op.execute("DROP FUNCTION IF EXISTS prevent_immutable_record_modification();")
