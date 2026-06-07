from __future__ import annotations
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Float, DateTime, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.match import Match


class MatchPrediction(Base):
    __tablename__ = "match_predictions"
    __table_args__ = (UniqueConstraint("match_id", "model_version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(String(50), ForeignKey("matches.id"), nullable=False)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1.0")
    predicted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    prob_home_win: Mapped[float] = mapped_column(Float, nullable=False)
    prob_draw: Mapped[float] = mapped_column(Float, nullable=False)
    prob_away_win: Mapped[float] = mapped_column(Float, nullable=False)
    xg_home: Mapped[float] = mapped_column(Float, nullable=False)
    xg_away: Mapped[float] = mapped_column(Float, nullable=False)
    top_scorelines: Mapped[Optional[dict]] = mapped_column(JSONB)
    score_distribution: Mapped[Optional[dict]] = mapped_column(JSONB)
    explanation: Mapped[Optional[dict]] = mapped_column(JSONB)
    home_elo_at_prediction: Mapped[Optional[float]] = mapped_column(Float)
    away_elo_at_prediction: Mapped[Optional[float]] = mapped_column(Float)
    home_features_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB)
    away_features_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB)
    match: Mapped["Match"] = relationship("Match", back_populates="predictions")
