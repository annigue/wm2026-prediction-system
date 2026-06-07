"""
Odds Aggregator — normalisiert Marktquoten zu fairen Wahrscheinlichkeiten.

  1. Overround (Marge) entfernen → faire Markt-WS (delegiert an odds_normalizer)
  2. Graceful Degradation: ohne echte Quoten → None (BDE nutzt Fallback)
"""

from __future__ import annotations
from app.services import odds_provider
# Kanonische Normalisierung (Single Source of Truth) — keine duplizierte Logik mehr.
from app.services.odds_normalizer import remove_overround


def get_market_probabilities(home_name: str, away_name: str) -> dict | None:
    """Holt echte Marktquoten und normalisiert sie zu fairen Wahrscheinlichkeiten."""
    raw = odds_provider.find_match_odds(home_name, away_name)
    if not raw:
        return None

    fair_1x2 = remove_overround(raw, ["home", "draw", "away"])
    fair_ou  = None
    if "over25" in raw and "under25" in raw:
        ou = remove_overround(raw, ["over25", "under25"])
        if ou:
            fair_ou = {"over": ou["over25"], "under": ou["under25"]}

    overround = None
    if all(raw.get(k, 0) > 1 for k in ["home", "draw", "away"]):
        overround = round(sum(1.0 / raw[k] for k in ["home", "draw", "away"]), 4)

    return {
        "available":     True,
        "source":        "the-odds-api",
        "raw_odds":      raw,
        "fair_1x2":      fair_1x2,
        "fair_ou":       fair_ou,
        "overround_1x2": overround,
    }


def status() -> dict:
    """Status der Odds-Integration für Monitoring."""
    return {
        "api_key_configured": odds_provider.is_available(),
        "fallback_active":    not odds_provider.is_available(),
        "note": ("Echte Marktquoten aktiv" if odds_provider.is_available()
                 else "Kein Odds-API-Key — BDE nutzt fair-odds-Schätzung (Fallback)"),
    }
