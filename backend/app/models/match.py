from __future__ import annotations
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Float, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.team import Team, Group
    from app.models.prediction import MatchPrediction


class Venue(Base):
    __tablename__ = "venues"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[Optional[str]] = mapped_column(String(100))
    altitude_m: Mapped[int] = mapped_column(Integer, default=0)
    lat: Mapped[Optional[float]] = mapped_column(Float)
    lon: Mapped[Optional[float]] = mapped_column(Float)
    timezone: Mapped[Optional[str]] = mapped_column(String(50))
    capacity: Mapped[Optional[int]] = mapped_column(Integer)
    matches: Mapped[list["Match"]] = relationship("Match", back_populates="venue")


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    tournament: Mapped[str] = mapped_column(String(20), default="WC2026")
    stage: Mapped[str] = mapped_column(String(30), nullable=False)
    group_id: Mapped[Optional[str]] = mapped_column(String(5), ForeignKey("groups.id"), nullable=True)
    match_number: Mapped[Optional[int]] = mapped_column(Integer)
    home_team_id: Mapped[Optional[str]] = mapped_column(String(20), ForeignKey("teams.id"), nullable=True)
    away_team_id: Mapped[Optional[str]] = mapped_column(String(20), ForeignKey("teams.id"), nullable=True)
    venue_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("venues.id"), nullable=True)
    kickoff_utc: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="SCHEDULED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    group: Mapped[Optional["Group"]] = relationship("Group", back_populates="matches")
    home_team: Mapped[Optional["Team"]] = relationship("Team", foreign_keys=[home_team_id])
    away_team: Mapped[Optional["Team"]] = relationship("Team", foreign_keys=[away_team_id])
    venue: Mapped[Optional["Venue"]] = relationship(back_populates="matches")
    result: Mapped[Optional["MatchResult"]] = relationship("MatchResult", back_populates="match", uselist=False)
    predictions: Mapped[list["MatchPrediction"]] = relationship("MatchPrediction", back_populates="match")


class MatchResult(Base):
    __tablename__ = "match_results"
    match_id: Mapped[str] = mapped_column(String(50), ForeignKey("matches.id"), primary_key=True)
    home_goals: Mapped[int] = mapped_column(Integer, nullable=False)
    away_goals: Mapped[int] = mapped_column(Integer, nullable=False)
    home_goals_ht: Mapped[Optional[int]] = mapped_column(Integer)
    away_goals_ht: Mapped[Optional[int]] = mapped_column(Integer)
    went_to_extra_time: Mapped[bool] = mapped_column(Boolean, default=False)
    went_to_penalties: Mapped[bool] = mapped_column(Boolean, default=False)
    penalty_winner_id: Mapped[Optional[str]] = mapped_column(String(20), ForeignKey("teams.id"), nullable=True)
    home_xg: Mapped[Optional[float]] = mapped_column(Float)
    away_xg: Mapped[Optional[float]] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source: Mapped[Optional[str]] = mapped_column(String(50))
    match: Mapped["Match"] = relationship(back_populates="result")
    penalty_winner: Mapped[Optional["Team"]] = relationship("Team", foreign_keys=[penalty_winner_id])
