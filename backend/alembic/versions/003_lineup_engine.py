"""V2 lineup engine — additive player tables (V1 unberührt).

Revision ID: 003
Revises: 002
"""
import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "players",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("api_football_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("nation_team_id", sa.String(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("position", sa.String(length=20)),
        sa.Column("shirt_number", sa.Integer()),
        sa.Column("age", sa.Integer()),
        sa.Column("club", sa.String(length=140)),
        sa.Column("market_value_eur", sa.Float()),
        sa.Column("transfermarkt_name", sa.String(length=140)),
        sa.Column("value_matched", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("data_source", sa.String(length=60)),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_index("ix_players_api_football_id", "players", ["api_football_id"])
    op.create_index("ix_players_nation_team_id", "players", ["nation_team_id"])


def downgrade() -> None:
    op.drop_index("ix_players_nation_team_id", table_name="players")
    op.drop_index("ix_players_api_football_id", table_name="players")
    op.drop_table("players")
