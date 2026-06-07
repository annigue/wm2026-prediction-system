"""initial schema (model-basierte Baseline — keine Spalten-Drift)

Revision ID: 001
Revises:
Create Date: 2026-06-03

Baseline: erstellt alle Tabellen direkt aus den SQLAlchemy-Models (Base.metadata).
Damit kann 001 nie von den Models abweichen. Folge-Migrationen sind additiv.
"""
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.database import Base
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    from app.database import Base
    import app.models  # noqa: F401
    Base.metadata.drop_all(bind=op.get_bind())
