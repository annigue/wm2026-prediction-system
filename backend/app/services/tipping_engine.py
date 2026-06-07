"""
Tipping Engine — punktoptimaler Exakt-Tipp (Erwartungswert-Maximierung).

NICHT argmax(score_probability), sondern argmax_t EP(t) mit
  EP(t) = Σ_{(a,b)} P(a,b) · points(t, (a,b))
über die gesamte Poisson-Score-Verteilung.

Punkteschema (Kicktipp-Standard, konfigurierbar):
  exakt 4 · Tordifferenz 3 · Tendenz 2 · sonst 0

stateless, deterministisch, liest nur fertige Prognosen.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from app.config import settings


@dataclass
class TipRecommendation:
    match_id: str
    tip: str
    expected_points: float
    confidence: str
    rationale: str
    modal_score: str
    margin: float


def _points(tip: tuple[int, int], actual: tuple[int, int]) -> int:
    """Punkte für einen Tipp gegen ein tatsächliches Ergebnis (Kicktipp-Standard)."""
    ti, tj = tip
    ai, aj = actual
    if ti == ai and tj == aj:
        return settings.tip_points_exact
    tip_diff = ti - tj
    act_diff = ai - aj
    if tip_diff == act_diff:          # gleiche Tordifferenz (inkl. beide Remis)
        return settings.tip_points_diff
    if (tip_diff > 0 and act_diff > 0) or (tip_diff < 0 and act_diff < 0):
        return settings.tip_points_tendency
    return 0


def _expected_points(tip: tuple[int, int], dist: dict[str, float]) -> float:
    ep = 0.0
    for score, p in dist.items():
        a, b = score.split(":")
        ep += p * _points(tip, (int(a), int(b)))
    return ep


def _rationale(best: str, best_ep: float, modal: str, modal_p: float, margin: float) -> str:
    base = f"Tipp {best} maximiert die erwarteten Punkte ({best_ep:.2f})."
    if best != modal:
        base += (f" Das modale Ergebnis wäre {modal} ({modal_p * 100:.0f}%), aber {best} "
                 f"deckt Tendenz und Tordifferenz robuster ab und bringt im Schnitt mehr Punkte.")
    else:
        base += f" Deckt sich mit dem wahrscheinlichsten Ergebnis ({modal_p * 100:.0f}%)."
    if margin < 0.05:
        base += " (Knappe Entscheidung gegenüber dem Zweitplatzierten.)"
    return base


def generate_tip(match_id: str, score_distribution: dict[str, float],
                 top_scorelines: list[dict] | None = None) -> TipRecommendation | None:
    """Berechnet den punktoptimalen Exakt-Tipp aus der Score-Verteilung."""
    if not score_distribution:
        return None
    max_g = settings.tip_max_goals
    candidates = []
    for i in range(max_g + 1):
        for j in range(max_g + 1):
            ep = _expected_points((i, j), score_distribution)
            candidates.append(((i, j), ep))
    candidates.sort(key=lambda c: c[1], reverse=True)
    best, best_ep = candidates[0]
    second, sec_ep = candidates[1]
    margin = best_ep - sec_ep
    modal_score, modal_p = max(score_distribution.items(), key=lambda kv: kv[1])

    if best_ep >= 2.3 and margin >= 0.15:
        confidence = "HIGH"
    elif best_ep >= 1.8:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    best_str = f"{best[0]}:{best[1]}"
    rationale = _rationale(best_str, best_ep, modal_score, modal_p, margin)
    return TipRecommendation(
        match_id=match_id,
        tip=best_str,
        expected_points=round(best_ep, 3),
        confidence=confidence,
        rationale=rationale,
        modal_score=modal_score,
        margin=round(margin, 3),
    )


async def generate_tip_for_match(match_id: str, db) -> dict | None:
    """Lädt die neueste Prognose und berechnet den optimalen Tipp."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.match import Match

    q = await db.execute(
        select(Match).options(selectinload(Match.predictions)).where(Match.id == match_id)
    )
    match = q.scalar_one_or_none()
    if not match or not match.predictions:
        return None
    pred = sorted(match.predictions, key=lambda p: p.predicted_at, reverse=True)[0]
    rec = generate_tip(match_id, pred.score_distribution or {}, pred.top_scorelines or [])
    return asdict(rec) if rec else None
