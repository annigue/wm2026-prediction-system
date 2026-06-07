"""
Market Calibration Service (OPTIONAL monitoring) — Modell vs. Markt.

Reines Monitoring — verändert WEDER Modell NOCH Quoten NOCH Empfehlungen.
Markt-Odds = informativer, aber verrauschter Prior, KEINE Ground Truth.

  - KL-Divergenz D(model‖market) / D(market‖model)
  - mittlerer |Edge|
  - Brier-Score (nur wenn echte Ergebnisse vorliegen)
"""

from __future__ import annotations
import math

_EPS = 1e-9


def kl_divergence(p: list[float], q: list[float]) -> float:
    total = 0.0
    for pi, qi in zip(p, q):
        pi = max(pi, _EPS)
        qi = max(qi, _EPS)
        total += pi * math.log(pi / qi)
    return round(total, 6)


def brier_score(probs: list[float], outcome_index: int) -> float:
    return round(sum((p - (1.0 if i == outcome_index else 0.0)) ** 2
                     for i, p in enumerate(probs)), 6)


def compare_match(model_probs: list[float], market_probs: list[float],
                  outcome_index: int | None = None) -> dict:
    res = {
        "kl_model_market": kl_divergence(model_probs, market_probs),
        "kl_market_model": kl_divergence(market_probs, model_probs),
        "mean_abs_edge":   round(sum(abs(m - k) for m, k in zip(model_probs, market_probs))
                                 / len(model_probs), 4),
        "edges": [round(m - k, 4) for m, k in zip(model_probs, market_probs)],
    }
    if outcome_index is not None:
        res["brier_model"]  = brier_score(model_probs, outcome_index)
        res["brier_market"] = brier_score(market_probs, outcome_index)
        res["brier_diff"]   = round(res["brier_model"] - res["brier_market"], 6)
    return res


def build_calibration_report(session) -> dict:
    """Aggregiert Modell-vs-Markt über alle Spiele mit ECHTEN Marktquoten. Read-only."""
    from sqlalchemy import text
    from app.services.odds_aggregator import get_market_probabilities

    rows = session.execute(text("""
        SELECT m.id, COALESCE(ht.home_country, ht.name), COALESCE(at.home_country, at.name),
               p.prob_home_win, p.prob_draw, p.prob_away_win,
               mr.home_goals, mr.away_goals
        FROM   matches m
        JOIN   teams ht ON ht.id = m.home_team_id
        JOIN   teams at ON at.id = m.away_team_id
        JOIN   LATERAL (SELECT prob_home_win, prob_draw, prob_away_win
                        FROM match_predictions WHERE match_id = m.id
                        ORDER BY predicted_at DESC LIMIT 1) p ON true
        LEFT   JOIN match_results mr ON mr.match_id = m.id
        WHERE  m.home_team_id IS NOT NULL AND m.away_team_id IS NOT NULL
    """)).fetchall()

    per_match = []
    for mid, hn, an, ph, pd, pa, hg, ag in rows:
        market = get_market_probabilities(hn, an)
        if not market or not market.get("fair_1x2"):
            continue
        f = market["fair_1x2"]
        market_probs = [f["home"], f["draw"], f["away"]]
        model_probs  = [float(ph), float(pd), float(pa)]
        outcome = None
        if hg is not None and ag is not None:
            outcome = 0 if hg > ag else (1 if hg == ag else 2)
        cmp = compare_match(model_probs, market_probs, outcome)
        cmp.update({"match_id": mid, "home": hn, "away": an})
        per_match.append(cmp)

    n = len(per_match)
    if n == 0:
        return {"available": False,
                "reason": "Keine echten Marktquoten verfügbar (Odds-API-Key fehlt oder keine Treffer).",
                "n_matches": 0}

    def _mean(key):
        vals = [m[key] for m in per_match if key in m]
        return round(sum(vals) / len(vals), 6) if vals else None

    scored = [m for m in per_match if "brier_model" in m]
    return {
        "available": True,
        "n_matches": n,
        "n_with_results": len(scored),
        "mean_kl_model_market": _mean("kl_model_market"),
        "mean_abs_edge":        _mean("mean_abs_edge"),
        "mean_brier_model":     round(sum(m["brier_model"] for m in scored) / len(scored), 6) if scored else None,
        "mean_brier_market":    round(sum(m["brier_market"] for m in scored) / len(scored), 6) if scored else None,
        "note": ("Markt-Odds sind ein informativer Prior, KEINE Ground Truth — "
                 "reines Monitoring, beeinflusst das Modell nicht."),
        "per_match": per_match[:50],
    }
