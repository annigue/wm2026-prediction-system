"""hardening indexes (Performance)

Revision ID: 002
Revises: 001
Create Date: 2026-06-06

Zusätzliche Indizes für häufige Queries. Idempotent (IF NOT EXISTS) — sicher auch
auf einer DB, die ursprünglich via create_all aufgebaut wurde.
"""
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_matches_stage_status ON matches (stage, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_team_features_latest "
               "ON team_features (team_id, snapshot_date DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_matches_stage_status")
    op.execute("DROP INDEX IF EXISTS idx_team_features_latest")
