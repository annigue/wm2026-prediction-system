"""Forecast Service — offizielle Prognose (Variante D) + Markt-Kalibrierung (log-Blend).

Nicht-invasiv: arbeitet ausschließlich auf der bereits berechneten Poisson/DC-Score-Verteilung.
Elo, Poisson und Dixon-Coles bleiben unverändert. Das REINE Modell (top-level prob_* der
MatchPrediction) bleibt erhalten und wird weiterhin von der Betting Engine genutzt (Edge/EV).
Hier wird daraus die OFFIZIELLE, markt-kalibrierte Prognose abgeleitet.

Pipeline:
  1. W/U/N mit Markt blenden (log-Opinion-Pool, Gewicht w)
  2. Score-Verteilung so reskalieren, dass ihre Regionen-Summen den geblendeten W/U/N entsprechen
  3. offizielle Tendenz = argmax(kalibrierte W/U/N), offizielles Ergebnis = bedingter Modus
  4. Vertrauen + Markt-Übereinstimmung als qualitative Indikatoren
"""
from __future__ import annotations

from app.config import settings

_EPS = 1e-12
_OUTCOMES = ("home", "draw", "away")


def _region(score: str) -> int:
    """0 = Heimsieg, 1 = Remis, 2 = Auswärtssieg."""
    i, j = (int(x) for x in score.split(":"))
    return 0 if i > j else (1 if i == j else 2)


def blend_1x2(model: list[float], market: list[float], w: float) -> list[float]:
    """Logarithmischer Opinion-Pool: p ∝ p_model^(1−w) · p_market^w, normiert."""
    if not market or w <= 0:
        return list(model)
    blended = [(max(m, _EPS) ** (1.0 - w)) * (max(k, _EPS) ** w)
               for m, k in zip(model, market)]
    s = sum(blended)
    return [b / s for b in blended] if s > 0 else list(model)


def reweight_distribution(dist: dict[str, float], target_1x2: list[float]) -> dict[str, float]:
    """Skaliert die 3 Ergebnis-Regionen des Score-Gitters auf die Ziel-W/U/N.
    Die Form INNERHALB jeder Region (welcher Score bei einem Heimsieg) bleibt Poisson/DC."""
    region_sum = [0.0, 0.0, 0.0]
    for k, p in dist.items():
        region_sum[_region(k)] += p
    factor = [(target_1x2[r] / region_sum[r]) if region_sum[r] > _EPS else 0.0 for r in range(3)]
    out = {k: p * factor[_region(k)] for k, p in dist.items()}
    s = sum(out.values())
    return {k: v / s for k, v in out.items()} if s > 0 else dict(dist)


def _conditional_mode(dist: dict[str, float], outcome: int) -> str:
    """Wahrscheinlichstes Einzelergebnis INNERHALB der vorhergesagten Tendenz."""
    cand = [(k, p) for k, p in dist.items() if _region(k) == outcome]
    pool = cand or list(dist.items())
    return max(pool, key=lambda x: x[1])[0]


def _expected_goals(dist: dict[str, float]) -> tuple[float, float]:
    eh = ea = 0.0
    for k, p in dist.items():
        i, j = (int(x) for x in k.split(":"))
        eh += i * p
        ea += j * p
    return round(eh, 2), round(ea, 2)


def _confidence(probs: list[float], divergence: float | None) -> tuple[str, float]:
    d = max(probs)
    level = "hoch" if d >= settings.conf_high else ("mittel" if d >= settings.conf_mid else "niedrig")
    if divergence is not None and divergence > settings.div_strong:
        level = {"hoch": "mittel", "mittel": "niedrig", "niedrig": "niedrig"}[level]
    return level, round(d, 4)


def _agreement(divergence: float | None) -> str:
    if divergence is None:
        return "kein_markt"
    if divergence <= settings.div_confirm:
        return "bestaetigt"
    if divergence <= settings.div_strong:
        return "leicht"
    return "stark"


def build_official_forecast(
    model_probs: list[float],
    model_dist: dict[str, float],
    market_probs: list[float] | None = None,
    w: float | None = None,
) -> dict:
    """Offizielle, markt-kalibrierte Prognose. Verändert das reine Modell nicht.

    model_probs:  [home, draw, away] (rein, Poisson/DC)
    model_dist:   Score-Verteilung "i:j" -> p (rein)
    market_probs: [home, draw, away] fair (vig-bereinigt) oder None
    """
    w = settings.odds_blend_weight if w is None else w

    if market_probs:
        cal_probs = blend_1x2(model_probs, market_probs, w)
        cal_dist = reweight_distribution(model_dist, cal_probs)
        divergence = 0.5 * sum(abs(m - k) for m, k in zip(model_probs, market_probs))
    else:
        cal_probs = list(model_probs)
        cal_dist = dict(model_dist)
        divergence = None

    outcome = max(range(3), key=lambda i: cal_probs[i])
    score = _conditional_mode(cal_dist, outcome)
    xg_h, xg_a = _expected_goals(cal_dist)
    level, decisiveness = _confidence(cal_probs, divergence)
    top3 = sorted(cal_dist.items(), key=lambda x: x[1], reverse=True)[:3]

    return {
        "outcome": _OUTCOMES[outcome],
        "score": score,
        "prob": round(cal_probs[outcome], 4),
        "probs": {"home": round(cal_probs[0], 4), "draw": round(cal_probs[1], 4),
                  "away": round(cal_probs[2], 4)},
        "xg": {"home": xg_h, "away": xg_a},
        "top_scorelines": [{"score": k, "prob": round(p, 4)} for k, p in top3],
        "confidence": {"level": level, "decisiveness": decisiveness},
        "market": {
            "available": market_probs is not None,
            "weight": round(w, 3) if market_probs else 0.0,
            "fair_1x2": ({"home": round(market_probs[0], 4), "draw": round(market_probs[1], 4),
                          "away": round(market_probs[2], 4)} if market_probs else None),
            "divergence": round(divergence, 4) if divergence is not None else None,
            "agreement": _agreement(divergence),
        },
    }
