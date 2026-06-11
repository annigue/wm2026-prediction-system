"""V2 — Stärke-Kennzahl einer Startelf/Spielergruppe (Marktwert-basiert).

Designprinzipien (siehe docs/V2_LINEUP_ENGINE.md, Abschnitt D):
  - Diminishing Returns je Spieler:  s_i = (mv_in_mio)^ALPHA   (ALPHA<1)
  - Positionsgewichtung (mild, kein Star-Bonus → Overfitting vermeiden)
  - Bank/Tiefe trägt klein bei (BENCH_BETA über die besten Ersatzspieler)
Nur Spieler MIT Marktwert fließen ein; unbewertete werden ignoriert (→ ggf. V1-Fallback).
"""

ALPHA = 0.60          # Diminishing Returns
BENCH_BETA = 0.15     # Beitrag der Bank zur Team-Stärke
BENCH_TOP = 7

# API-Football liefert nur grobe Positionsgruppen → mildes Gewicht je Gruppe.
POSITION_WEIGHT = {
    "Goalkeeper": 1.00,
    "Defender":   1.00,
    "Midfielder": 1.05,
    "Attacker":   1.10,
}


def player_strength(market_value_eur) -> float | None:
    """s = (Marktwert in Mio €)^ALPHA. None, wenn kein Wert vorliegt."""
    if not market_value_eur or market_value_eur <= 0:
        return None
    return (market_value_eur / 1_000_000.0) ** ALPHA
