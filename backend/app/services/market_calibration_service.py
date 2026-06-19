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

from app.config import settings

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


def _load_scored_matches(session) -> list[tuple[list[float], list[float], int]]:
    """Liefert (model_probs, market_probs, outcome_index) für alle gespielten Spiele
    mit gespeichertem Markt-Snapshot."""
    from sqlalchemy import text

    rows = session.execute(text("""
        SELECT p.prob_home_win, p.prob_draw, p.prob_away_win, p.explanation,
               mr.home_goals, mr.away_goals
        FROM   matches m
        JOIN   LATERAL (SELECT prob_home_win, prob_draw, prob_away_win, explanation
                        FROM match_predictions WHERE match_id = m.id
                        ORDER BY predicted_at DESC LIMIT 1) p ON true
        JOIN   match_results mr ON mr.match_id = m.id
        WHERE  m.home_team_id IS NOT NULL AND m.away_team_id IS NOT NULL
               AND mr.home_goals IS NOT NULL
    """)).fetchall()

    result = []
    for ph, pd, pa, expl, hg, ag in rows:
        snap = ((expl or {}).get("official", {}) or {}).get("market") or {}
        f = snap.get("fair_1x2")
        if not f:
            continue
        model_probs = [float(ph), float(pd), float(pa)]
        market_probs = [f["home"], f["draw"], f["away"]]
        outcome = 0 if hg > ag else (1 if hg == ag else 2)
        result.append((model_probs, market_probs, outcome))
    return result


def compute_adaptive_weight(session) -> tuple[float, dict]:
    """Grid-Search über w ∈ [0.05, 0.60]: findet das Markt-Gewicht mit dem niedrigsten
    mittleren Brier-Score auf allen gespielten Spielen. Gibt (w_optimal, meta) zurück.
    Fällt auf settings.odds_blend_weight zurück bei zu wenig Daten."""
    from app.services.forecast_service import blend_1x2

    matches = _load_scored_matches(session)
    default_w = settings.odds_blend_weight
    min_n = settings.adaptive_blend_min_matches

    if len(matches) < min_n:
        return default_w, {
            "adaptive": False,
            "reason": f"Zu wenig gespielte Spiele mit Markt-Snapshot ({len(matches)}/{min_n})",
            "n_matches": len(matches),
            "weight_used": default_w,
        }

    candidates = [round(w / 100, 2) for w in range(5, 100, 5)]
    candidates = [0.0] + candidates

    brier_by_w = {}
    for w in candidates:
        total = 0.0
        for model_p, market_p, outcome in matches:
            blended = blend_1x2(model_p, market_p, w)
            total += brier_score(blended, outcome)
        brier_by_w[w] = round(total / len(matches), 6)

    w_optimal = min(brier_by_w, key=brier_by_w.get)

    return w_optimal, {
        "adaptive": True,
        "n_matches": len(matches),
        "weight_used": w_optimal,
        "default_weight": default_w,
        "brier_at_default": brier_by_w.get(default_w),
        "brier_at_optimal": brier_by_w[w_optimal],
        "improvement": round((brier_by_w.get(default_w, 0) - brier_by_w[w_optimal]), 6),
        "brier_curve": {str(w): b for w, b in sorted(brier_by_w.items())},
    }


def build_calibration_report(session) -> dict:
    """Aggregiert Modell vs. Markt vs. geblendet. Nutzt den zum Prognosezeitpunkt
    gespeicherten Markt-SNAPSHOT (explanation.official.market) — für gespielte Spiele
    gibt es keine Live-Quoten mehr. Read-only, beeinflusst nichts."""
    from sqlalchemy import text
    from app.services.forecast_service import blend_1x2

    rows = session.execute(text("""
        SELECT m.id, ht.name, at.name,
               p.prob_home_win, p.prob_draw, p.prob_away_win, p.explanation,
               mr.home_goals, mr.away_goals
        FROM   matches m
        JOIN   teams ht ON ht.id = m.home_team_id
        JOIN   teams at ON at.id = m.away_team_id
        JOIN   LATERAL (SELECT prob_home_win, prob_draw, prob_away_win, explanation
                        FROM match_predictions WHERE match_id = m.id
                        ORDER BY predicted_at DESC LIMIT 1) p ON true
        LEFT   JOIN match_results mr ON mr.match_id = m.id
        WHERE  m.home_team_id IS NOT NULL AND m.away_team_id IS NOT NULL
    """)).fetchall()

    per_match = []
    for mid, hn, an, ph, pd, pa, expl, hg, ag in rows:
        snap = ((expl or {}).get("official", {}) or {}).get("market") or {}
        f = snap.get("fair_1x2")
        if not f:
            continue  # keine erfasste Markt-WS (Prognose vor der Markt-Integration)
        market_probs = [f["home"], f["draw"], f["away"]]
        model_probs  = [float(ph), float(pd), float(pa)]
        outcome = None
        if hg is not None and ag is not None:
            outcome = 0 if hg > ag else (1 if hg == ag else 2)
        cmp = compare_match(model_probs, market_probs, outcome)
        blended = blend_1x2(model_probs, market_probs, settings.odds_blend_weight)
        cmp["blended_probs"] = [round(b, 4) for b in blended]
        if outcome is not None:
            cmp["brier_blended"] = brier_score(blended, outcome)
        cmp.update({"match_id": mid, "home": hn, "away": an})
        per_match.append(cmp)

    n = len(per_match)
    if n == 0:
        return {"available": False,
                "reason": "Noch keine Prognosen mit erfasstem Markt-Snapshot (erst nach dem nächsten "
                          "predict-all-Lauf mit aktiven Quoten verfügbar).",
                "n_matches": 0}

    def _mean(key):
        vals = [m[key] for m in per_match if key in m]
        return round(sum(vals) / len(vals), 6) if vals else None

    scored = [m for m in per_match if "brier_model" in m]
    bm = round(sum(m["brier_model"] for m in scored) / len(scored), 6) if scored else None
    bk = round(sum(m["brier_market"] for m in scored) / len(scored), 6) if scored else None
    bb = round(sum(m["brier_blended"] for m in scored) / len(scored), 6) if scored else None

    best = None
    if scored:
        best = min((("modell", bm), ("markt", bk), ("geblendet", bb)), key=lambda x: x[1])[0]

    adaptive_w, adaptive_meta = compute_adaptive_weight(session)

    return {
        "available": True,
        "n_matches": n,
        "n_with_results": len(scored),
        "blend_weight": settings.odds_blend_weight,
        "adaptive_weight": adaptive_meta,
        "mean_kl_model_market": _mean("kl_model_market"),
        "mean_abs_edge":        _mean("mean_abs_edge"),
        "mean_brier_model":     bm,
        "mean_brier_market":    bk,
        "mean_brier_blended":   bb,   # offizielle Prognose (Modell ⊕ Markt)
        "best_brier":           best,  # niedrigster Brier = beste Kalibrierung (bei genug Spielen)
        "note": ("Brier niedriger = besser. 'geblendet' ist die offizielle Prognose. "
                 "Bei <~15 Spielen ist der Vergleich noch verrauscht — nur Trend beachten. "
                 "Markt beeinflusst NUR die offizielle Prognose, NICHT Betting/Edge/EV."),
        "per_match": per_match[:50],
    }
