from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class AppState(Base):
    """Kleiner Key-Value-Speicher für persistente Laufzeit-Zustände (z. B. last_sync),
    die einen Backend-Neustart überleben müssen (Free-Tier startet häufig neu)."""
    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
