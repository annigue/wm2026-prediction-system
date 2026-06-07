"""
Decision Engine — kanonische öffentliche API der Entscheidungsschicht (Facade).

Bündelt die Kernfunktionen des Decision Layers und delegiert die Report-Erzeugung an
`betting_engine.py` (Single Source of Truth — keine Duplikation der Logik).

  EV   = (Modell-WS × Quote) − 1     → erwartete Auszahlung
  Edge = Modell-WS − Markt-WS        → Informationsvorsprung (overround-bereinigt)

stateless, deterministisch, additiv (kein Eingriff in Elo/Poisson).
"""

from __future__ import annotations
from typing import Optional

from app.services.betting_engine import (
    compute_ev as compute_expected_value,
    compute_edge,
    rank_bets_by_ev,
    classify_risk,
    implied_prob,
    fair_odds,
    BetOption,
    BettingReport,
    generate_report,
    report_to_dict,
    generate_betting_recommendations,
)
from app.services.odds_aggregator import remove_overround, get_market_probabilities

__all__ = [
    "compute_expected_value",
    "compute_edge",
    "rank_bets_by_ev",
    "classify_risk",
    "implied_prob",
    "fair_odds",
    "remove_overround",
    "get_market_probabilities",
    "BetOption",
    "BettingReport",
    "generate_report",
    "report_to_dict",
    "generate_recommendations",
]


async def generate_recommendations(
    match_id: str,
    db,
    odds: Optional[dict[str, float]] = None,
) -> Optional[BettingReport]:
    """Kanonischer Einstiegspunkt der Decision Engine (delegiert an betting_engine)."""
    return await generate_betting_recommendations(match_id, db, odds)
