"""V2 — Aufstellungs-Engine: Spieler-/Kaderdaten (additiv, V1 unberührt).

Diese Tabellen werden von V1 NIE gelesen. Quelle: API-Football (26er-WM-Kader) +
Transfermarkt (Marktwerte, gejoint über Name+Geburtsjahr). Siehe docs/V2_LINEUP_ENGINE.md.
"""
from datetime import datetime

from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Player(Base):
    """Ein WM-Kaderspieler (= 48 Kader à ~26). Trägt API-Football-Identität + Transfermarkt-Wert."""
    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String, primary_key=True)            # f"af{api_football_id}"
    api_football_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(140))
    nation_team_id: Mapped[str] = mapped_column(String, ForeignKey("teams.id"), index=True)

    position: Mapped[str | None] = mapped_column(String(20))             # GK/Defender/Midfielder/Attacker
    shirt_number: Mapped[int | None] = mapped_column(Integer)
    age: Mapped[int | None] = mapped_column(Integer)
    club: Mapped[str | None] = mapped_column(String(140))

    market_value_eur: Mapped[float | None] = mapped_column(Float)        # aus Transfermarkt (gejoint)
    transfermarkt_name: Mapped[str | None] = mapped_column(String(140))
    value_matched: Mapped[bool] = mapped_column(Boolean, default=False)

    data_source: Mapped[str] = mapped_column(String(60), default="apifootball+transfermarkt")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
