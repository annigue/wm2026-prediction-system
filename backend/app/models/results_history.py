from __future__ import annotations
from datetime import date as _date
from typing import Optional
from sqlalchemy import String, Integer, Date, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class InternationalResult(Base):
    """Historische Länderspiel-Ergebnisse (NUR Tore) als Datenbasis für Attack-/Defense-Ratings.

    Quelle: martj42/international_results (öffentlich, reine Spielergebnisse — keine Spieler-,
    SPI- oder Nebendaten). Getrennt von den WM-`matches`. Opponent kann ein Nicht-WM-Team sein
    (dann bleibt dessen *_team_id NULL); für die Ratings zählen die Spiele der WM-Teams.
    """
    __tablename__ = "international_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_date: Mapped[_date] = mapped_column(Date, index=True)
    home_name: Mapped[str] = mapped_column(String(80))
    away_name: Mapped[str] = mapped_column(String(80))
    home_team_id: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    away_team_id: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    home_goals: Mapped[int] = mapped_column(Integer)
    away_goals: Mapped[int] = mapped_column(Integer)
    tournament: Mapped[Optional[str]] = mapped_column(String(80))
    neutral: Mapped[bool] = mapped_column(Boolean, default=False)
