"""
Form Engine — Single Source of Truth für Team-Form.

Form wird AUSSCHLIESSLICH deterministisch aus realen Spielergebnissen berechnet —
keine Seed-Werte, keine Schätzungen, kein Modell-Coupling.

Definition (form_engine_v2):
    - Punkte:        Sieg = 3, Remis = 1, Niederlage = 0
    - Tore:          erzielte und kassierte Tore (über die Tordifferenz)
    - Recency-Decay: weight_i = decay^i (jüngere Spiele höher gewichtet)

    points_term = (Ø Punkte / 3) · 2 − 1            # 0 Pkt → −1, 3 Pkt → +1
    gd_term     = clamp(Ø Tordifferenz / 3, −1, +1)  # ±3 Tore/Spiel sättigt
    form_score  = 0.5 · points_term + 0.5 · gd_term  ∈ [−1, +1]

Ohne Ergebnisse exakt 0.0 (neutral). Auto-Update nach jedem Ergebnis.
"""

from __future__ import annotations
from dataclasses import dataclass
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings


@dataclass
class FormResult:
    team_id:    str
    form_score: float          # [-1, 1]
    form_index: int            # [-100, 100]
    n_matches:  int
    detail:     list[dict]


def compute_form(team_id: str, session: Session) -> FormResult:
    """Form aus den letzten N realen Ergebnissen (Punkte + Tore + Recency)."""
    n     = settings.form_n_matches
    decay = settings.form_decay

    rows = session.execute(text("""
        SELECT
            CASE WHEN m.home_team_id = :tid THEN mr.home_goals ELSE mr.away_goals END AS gf,
            CASE WHEN m.home_team_id = :tid THEN mr.away_goals ELSE mr.home_goals END AS ga,
            CASE WHEN m.home_team_id = :tid THEN m.away_team_id ELSE m.home_team_id END AS opp_id,
            m.kickoff_utc
        FROM   matches m
        JOIN   match_results mr ON mr.match_id = m.id
        WHERE  (m.home_team_id = :tid OR m.away_team_id = :tid)
          AND  m.home_team_id IS NOT NULL
          AND  m.away_team_id IS NOT NULL
        ORDER  BY m.kickoff_utc DESC
        LIMIT  :n
    """), {"tid": team_id, "n": n}).fetchall()

    if not rows:
        return FormResult(team_id=team_id, form_score=0.0, form_index=0,
                          n_matches=0, detail=[])

    weighted_pts = 0.0
    weighted_gd  = 0.0
    weight_total = 0.0
    detail: list[dict] = []

    for i, row in enumerate(rows):
        gf, ga, opp_id = int(row[0]), int(row[1]), row[2]
        points = 3.0 if gf > ga else (1.0 if gf == ga else 0.0)
        gd     = gf - ga
        weight = decay ** i

        weighted_pts += weight * points
        weighted_gd  += weight * gd
        weight_total += weight
        detail.append({
            "opponent": opp_id,
            "score":    f"{gf}:{ga}",
            "result":   "W" if points == 3.0 else ("D" if points == 1.0 else "L"),
            "points":   points,
            "goal_diff": gd,
            "weight":   round(weight, 3),
        })

    avg_points = weighted_pts / weight_total
    avg_gd     = weighted_gd / weight_total

    points_term = (avg_points / 3.0) * 2.0 - 1.0
    gd_term     = max(-1.0, min(1.0, avg_gd / 3.0))
    form_score  = max(-1.0, min(1.0, 0.5 * points_term + 0.5 * gd_term))

    return FormResult(
        team_id=team_id,
        form_score=round(form_score, 4),
        form_index=round(form_score * 100),
        n_matches=len(rows),
        detail=detail,
    )


def update_team_form(team_id: str, session: Session) -> FormResult:
    """Berechnet die Form neu und schreibt form_score in team_features."""
    result = compute_form(team_id, session)
    session.execute(text("""
        UPDATE team_features
        SET    form_score = :fs, data_source = 'form_engine_v2'
        WHERE  team_id = :tid
          AND  snapshot_date = (
                   SELECT MAX(snapshot_date) FROM team_features WHERE team_id = :tid
               )
    """), {"fs": result.form_score, "tid": team_id})
    return result


def update_all_forms(session: Session) -> list[FormResult]:
    """Aktualisiert die Form aller Teams mit mindestens einem Ergebnis."""
    rows = session.execute(text("""
        SELECT DISTINCT unnest(ARRAY[home_team_id, away_team_id]) AS tid
        FROM   matches m
        JOIN   match_results mr ON mr.match_id = m.id
        WHERE  home_team_id IS NOT NULL AND away_team_id IS NOT NULL
    """)).fetchall()

    results = []
    for r in rows:
        if r[0]:
            results.append(update_team_form(r[0], session))
    return results
