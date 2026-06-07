from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class TournamentSimulation(Base):
    __tablename__ = "tournament_simulations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)
    n_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=100000)
    simulated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    champion_probs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    stage_probs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    group_probs: Mapped[Optional[dict]] = mapped_column(JSONB)
    tournament_state_hash: Mapped[Optional[str]] = mapped_column(String(64))
    triggered_by: Mapped[Optional[str]] = mapped_column(String(50))
