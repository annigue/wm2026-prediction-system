"""Attack-/Defense-Ratings aus historischen Länderspiel-Ergebnissen (international_results).

Vollständig datengetrieben (nur Tore), keine Schätzwerte:
  - relativ zum globalen Tor-Schnitt μ (Tore pro Team und Spiel)
  - Recency-Gewichtung wie die Form-Engine (weight_i = decay^i)
  - Shrinkage zum Neutralwert 1.0 gegen kleine Stichproben

attack_rating > 1  → offensivstärker als Schnitt
defense_rating < 1 → defensivstärker als Schnitt (weniger Gegentore)

Elo bleibt der dominante Faktor; diese Ratings modulieren λ nur gedämpft (siehe poisson_model, ad_gamma).
"""
from __future__ import annotations

from sqlalchemy import text

from app.config import settings


def global_mean_goals(session) -> float:
    """μ = durchschnittliche Tore pro Team und Spiel über alle erfassten Ergebnisse."""
    mu = session.execute(text("""
        SELECT avg(g) FROM (
            SELECT home_goals AS g FROM international_results
            UNION ALL SELECT away_goals FROM international_results
        ) x
    """)).scalar()
    return float(mu) if mu else 1.30


def compute_ratings(session) -> dict[str, dict]:
    """Berechnet {team_id: {attack, defense, n}} für alle Teams. Read-only."""
    mu = global_mean_goals(session)
    decay, n_win, k = settings.ad_decay, settings.ad_window, settings.ad_shrinkage_k
    lo, hi = settings.ad_clamp_lo, settings.ad_clamp_hi

    team_ids = [r[0] for r in session.execute(text("SELECT id FROM teams"))]
    out: dict[str, dict] = {}
    for tid in team_ids:
        # Historie (martj42) OHNE die finale WM 2026 + UNSERE eigenen WM-Ergebnisse
        # (frisch synchronisiert) → Ratings reagieren nach jedem WM-Spiel; keine Doppelzählung.
        rows = session.execute(text("""
            SELECT gf, ga FROM (
                SELECT match_date,
                       CASE WHEN home_team_id = :t THEN home_goals ELSE away_goals END AS gf,
                       CASE WHEN home_team_id = :t THEN away_goals ELSE home_goals END AS ga
                FROM   international_results
                WHERE  (home_team_id = :t OR away_team_id = :t)
                  AND  NOT (tournament = 'FIFA World Cup' AND match_date >= '2026-06-01')
                UNION ALL
                SELECT m.kickoff_utc::date,
                       CASE WHEN m.home_team_id = :t THEN mr.home_goals ELSE mr.away_goals END,
                       CASE WHEN m.home_team_id = :t THEN mr.away_goals ELSE mr.home_goals END
                FROM   matches m JOIN match_results mr ON mr.match_id = m.id
                WHERE  m.home_team_id = :t OR m.away_team_id = :t
            ) x
            ORDER BY match_date DESC
            LIMIT  :n
        """), {"t": tid, "n": n_win}).all()

        if not rows:
            out[tid] = {"attack": 1.0, "defense": 1.0, "n": 0}
            continue

        wsum = gf_w = ga_w = 0.0
        for i, (gf, ga) in enumerate(rows):
            w = decay ** i
            wsum += w
            gf_w += w * gf
            ga_w += w * ga

        # Shrinkage zum Neutralwert μ, dann relativ zu μ:
        atk = (gf_w + k * mu) / (wsum + k) / mu
        dfn = (ga_w + k * mu) / (wsum + k) / mu
        out[tid] = {
            "attack": round(max(lo, min(hi, atk)), 3),
            "defense": round(max(lo, min(hi, dfn)), 3),
            "n": len(rows),
        }
    return out


def refresh_ratings(session) -> int:
    """Berechnet Attack/Defense neu und schreibt sie in den neuesten team_features-Snapshot.
    Wird nach jedem Ergebnis aufgerufen (Recompute-Kette) → Ratings bleiben aktuell. Idempotent."""
    ratings = compute_ratings(session)
    upd = 0
    for tid, r in ratings.items():
        upd += session.execute(text("""
            UPDATE team_features SET attack_rating = :a, defense_rating = :d
            WHERE team_id = :t
              AND snapshot_date = (SELECT max(snapshot_date) FROM team_features WHERE team_id = :t)
        """), {"a": r["attack"], "d": r["defense"], "t": tid}).rowcount
    return upd
