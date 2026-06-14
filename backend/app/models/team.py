from __future__ import annotations
from datetime import datetime, date
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Float, Integer, DateTime, Date, ForeignKey, Table, Column, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.match import Match

group_memberships = Table(
    "group_memberships",
    Base.metadata,
    Column("group_id", String(5), ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    Column("team_id", String(20), ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True),
)


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    short_name: Mapped[str] = mapped_column(String(10), nullable=False)
    flag_emoji: Mapped[Optional[str]] = mapped_column(String(10))
    confederation: Mapped[Optional[str]] = mapped_column(String(20))
    home_country: Mapped[Optional[str]] = mapped_column(String(100))
    home_lat: Mapped[Optional[float]] = mapped_column(Float)
    home_lon: Mapped[Optional[float]] = mapped_column(Float)
    home_altitude_m: Mapped[int] = mapped_column(Integer, default=0)
    home_timezone: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    features: Mapped[List["TeamFeature"]] = relationship(
        back_populates="team", order_by="TeamFeature.snapshot_date.desc()", lazy="selectin")
    elo_history: Mapped[List["EloRating"]] = relationship(
        back_populates="team", order_by="EloRating.created_at.desc()", lazy="selectin")
    groups: Mapped[List["Group"]] = relationship(
        secondary=group_memberships, back_populates="teams", lazy="selectin")


class TeamFeature(Base):
    __tablename__ = "team_features"
    __table_args__ = (UniqueConstraint("team_id", "snapshot_date"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[str] = mapped_column(String(20), ForeignKey("teams.id"), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    fifa_ranking: Mapped[Optional[int]] = mapped_column(Integer)
    fifa_points: Mapped[Optional[float]] = mapped_column(Float)
    elo_rating: Mapped[float] = mapped_column(Float, nullable=False, default=1500)
    market_value_millions: Mapped[Optional[float]] = mapped_column(Float)
    avg_squad_age: Mapped[Optional[float]] = mapped_column(Float)
    avg_caps_per_player: Mapped[Optional[float]] = mapped_column(Float)
    form_score: Mapped[Optional[float]] = mapped_column(Float, default=0)
    form_goals_scored_avg: Mapped[Optional[float]] = mapped_column(Float)
    form_goals_conceded_avg: Mapped[Optional[float]] = mapped_column(Float)
    # Attack-/Defense-Ratings aus historischen Ergebnissen (relativ zum Tor-Schnitt, ~1.0 neutral)
    attack_rating: Mapped[Optional[float]] = mapped_column(Float)
    defense_rating: Mapped[Optional[float]] = mapped_column(Float)
    data_source: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    team: Mapped["Team"] = relationship(back_populates="features")


class EloRating(Base):
    __tablename__ = "elo_ratings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[str] = mapped_column(String(20), ForeignKey("teams.id"), nullable=False)
    rating: Mapped[float] = mapped_column(Float, nullable=False)
    match_id: Mapped[Optional[str]] = mapped_column(String(50))
    reason: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    team: Mapped["Team"] = relationship(back_populates="elo_history")


class Group(Base):
    __tablename__ = "groups"
    id: Mapped[str] = mapped_column(String(5), primary_key=True)
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    teams: Mapped[List["Team"]] = relationship(
        secondary=group_memberships, back_populates="groups", lazy="selectin")
    matches: Mapped[List["Match"]] = relationship("Match", back_populates="group")
