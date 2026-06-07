"""
Odds Normalizer — kanonische Umrechnung Quote → Wahrscheinlichkeit.

SINGLE SOURCE OF TRUTH für Overround-Entfernung (Vig-Bereinigung). Wird sowohl vom
`odds_aggregator` als auch von der `betting_engine` genutzt — keine duplizierte Logik.

    p_raw_i   = 1 / odds_i            implizite WS (enthält Overround/Marge)
    overround = Σ p_raw_i             > 1 (Buchmacher-Marge)
    p_fair_i  = p_raw_i / overround   vig-bereinigte faire WS, Σ = 1
"""

from __future__ import annotations


def implied_probability(odds: float | None) -> float | None:
    """1/odds (enthält noch Overround). None bei ungültiger Quote."""
    if odds is None or odds <= 1.0:
        return None
    return 1.0 / odds


def overround(odds_values: list[float]) -> float | None:
    """Summe der impliziten WS = Marge (>1). None wenn eine Quote ungültig."""
    implied = [implied_probability(o) for o in odds_values]
    if any(p is None for p in implied):
        return None
    return sum(implied)  # type: ignore[arg-type]


def remove_overround(odds: dict[str, float], keys: list[str],
                     ndigits: int = 4) -> dict[str, float] | None:
    """Entfernt die Marge aus einer Quotengruppe → faire WS (Σ=1) oder None."""
    implied: dict[str, float] = {}
    for k in keys:
        p = implied_probability(odds.get(k))
        if p is None:
            return None
        implied[k] = p
    total = sum(implied.values())
    if total <= 0:
        return None
    return {k: round(v / total, ndigits) for k, v in implied.items()}


def normalize_list(odds_values: list[float]) -> list[float] | None:
    """Wie remove_overround, aber für eine Werteliste (Reihenfolge erhalten)."""
    implied = [implied_probability(o) for o in odds_values]
    if any(p is None for p in implied):
        return None
    s = sum(implied)  # type: ignore[arg-type]
    return [p / s for p in implied] if s > 0 else None  # type: ignore[operator]


def market_baseline(odds: dict[str, float], keys: list[str]) -> dict | None:
    """Vollständige Markt-Baseline: raw_implied, fair (Σ=1), overround. None bei Unsinn."""
    fair = remove_overround(odds, keys)
    if fair is None:
        return None
    raw = {k: round(implied_probability(odds[k]), 4) for k in keys}  # type: ignore[arg-type]
    return {
        "raw_implied": raw,
        "fair":        fair,
        "overround":   round(sum(raw.values()), 4),
    }
