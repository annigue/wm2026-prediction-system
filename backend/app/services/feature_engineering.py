"""
Feature Engineering Layer — Klassifikation der Features nach Datenherkunft.

  COMPUTED  — deterministisch aus Spielergebnissen (form_score via form_engine, goals_avg)
  PRIOR     — externe statische Eingaben (market_value, age, caps, fifa_ranking)
  DERIVED   — aus team+venue Koordinaten (altitude_delta, travel) in feature_adjuster

Form wird an die kanonische form_engine delegiert (Single Source of Truth).
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

GOALS_N_GAMES = 3
FORM_N_GAMES = 6  # nur für Reporting

FEATURE_CLASSIFICATION = {
    "form_score": {
        "type":   "COMPUTED",
        "source": "form_engine (opponent-unabhängig: Punkte+Tore) aus match_results — Single Source of Truth",
        "update": "Automatisch nach jedem Ergebnis",
        "before_wm": "0.0 (neutral) — kein Seed-Schätzwert mehr",
    },
    "form_goals_scored_avg": {
        "type": "COMPUTED", "source": "WM-Spielergebnisse",
        "update": "Automatisch nach jedem Ergebnis", "before_wm": "None → nicht genutzt",
    },
    "form_goals_conceded_avg": {
        "type": "COMPUTED", "source": "WM-Spielergebnisse",
        "update": "Automatisch nach jedem Ergebnis", "before_wm": "None → nicht genutzt",
    },
    "market_value_millions": {
        "type": "PRIOR", "source": "Seed (Transfermarkt, April 2026)",
        "update": "Manuell, bei Bedarf", "before_wm": "Statisch (eingefroren)",
    },
    "avg_squad_age": {
        "type": "PRIOR", "source": "Seed", "update": "Einmalig",
        "before_wm": "Statisch (nicht mehr im Modell)",
    },
    "avg_caps_per_player": {
        "type": "PRIOR", "source": "Seed", "update": "Einmalig",
        "before_wm": "Statisch (nicht mehr im Modell)",
    },
    "fifa_ranking": {
        "type": "PRIOR", "source": "Seed (FIFA-Rangliste)",
        "update": "Einmalig (nur Elo-Init-Prior)", "before_wm": "Statisch",
    },
    "elo_rating": {
        "type": "COMPUTED", "source": "Bayesian Update nach jedem Ergebnis (EloModel) / eloratings.net-Init",
        "update": "Automatisch nach jedem Ergebnis", "before_wm": "eloratings.net",
    },
}


def compute_goals_averages(team_id: str, session: Session, n: int = GOALS_N_GAMES) -> dict:
    """Tore-Durchschnitt aus den letzten n WM-Spielen."""
    rows = session.execute(text("""
        SELECT
            CASE WHEN m.home_team_id = :tid THEN mr.home_goals ELSE mr.away_goals END AS scored,
            CASE WHEN m.home_team_id = :tid THEN mr.away_goals ELSE mr.home_goals END AS conceded
        FROM   matches m
        JOIN   match_results mr ON mr.match_id = m.id
        WHERE  m.tournament = 'WC2026'
          AND  (m.home_team_id = :tid OR m.away_team_id = :tid)
        ORDER  BY m.kickoff_utc DESC
        LIMIT  :n
    """), {"tid": team_id, "n": n}).fetchall()

    if not rows:
        return {"scored_avg": None, "conceded_avg": None}
    scored   = round(sum(float(r[0]) for r in rows) / len(rows), 2)
    conceded = round(sum(float(r[1]) for r in rows) / len(rows), 2)
    return {"scored_avg": scored, "conceded_avg": conceded}


def refresh_team_features(team_id: str, session: Session) -> dict:
    """COMPUTED-Features neu berechnen. Form → form_engine (Single Source of Truth)."""
    from sqlalchemy import select
    from app.models.team import TeamFeature
    from app.services.form_engine import update_team_form

    form_result = update_team_form(team_id, session)
    goals = compute_goals_averages(team_id, session)

    feat = session.execute(
        select(TeamFeature)
        .where(TeamFeature.team_id == team_id)
        .order_by(TeamFeature.snapshot_date.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not feat:
        return {"skipped": "Keine TeamFeature gefunden"}

    updates: dict[str, object] = {
        "form_score": form_result.form_score,
        "form_n_matches": form_result.n_matches,
    }
    if goals["scored_avg"] is not None:
        feat.form_goals_scored_avg   = goals["scored_avg"]
        feat.form_goals_conceded_avg = goals["conceded_avg"]
        updates["form_goals_scored_avg"]   = goals["scored_avg"]
        updates["form_goals_conceded_avg"] = goals["conceded_avg"]

    return {
        "team_id": team_id, "updated": updates,
        "source": "form_engine (Form) + WM match_results (goals_avg)",
        "n_games": GOALS_N_GAMES,
    }


def refresh_all_teams_with_results(session: Session) -> list[dict]:
    """Aktualisiert alle Teams, die bereits WM-Ergebnisse haben."""
    rows = session.execute(text("""
        SELECT DISTINCT unnest(ARRAY[home_team_id, away_team_id]) AS team_id
        FROM   matches m
        JOIN   match_results mr ON mr.match_id = m.id
        WHERE  m.tournament = 'WC2026'
          AND  home_team_id IS NOT NULL AND away_team_id IS NOT NULL
    """)).fetchall()
    results = []
    for row in rows:
        if row[0]:
            results.append(refresh_team_features(row[0], session))
    return results


def get_feature_audit(session: Session) -> dict:
    """Übersicht aller Features mit Klassifikation (Debugging/Transparenz)."""
    rows = session.execute(text("""
        SELECT t.id, t.name, tf.form_score, tf.market_value_millions, tf.avg_squad_age,
               tf.avg_caps_per_player, tf.fifa_ranking, tf.elo_rating, tf.data_source, tf.snapshot_date
        FROM   teams t
        JOIN   (SELECT DISTINCT ON (team_id) * FROM team_features
                ORDER BY team_id, snapshot_date DESC) tf ON tf.team_id = t.id
        ORDER  BY t.name
    """)).fetchall()

    teams_audit = []
    for r in rows:
        data_source = r[8] or ""
        form_is_computed = ("form_engine" in data_source or "feature_engineering" in data_source)
        teams_audit.append({
            "team_id": r[0], "name": r[1],
            "form_score": {
                "value": r[2],
                "type": "COMPUTED" if form_is_computed else "PRIOR_SEED",
                "note": "Aus WM-Ergebnissen berechnet" if form_is_computed
                        else f"Seed/Init ({data_source}) — wird nach 1. WM-Spiel überschrieben",
            },
            "market_value_millions": {"value": r[3], "type": "PRIOR"},
            "avg_squad_age":         {"value": r[4], "type": "PRIOR"},
            "avg_caps_per_player":   {"value": r[5], "type": "PRIOR"},
            "fifa_ranking":          {"value": r[6], "type": "PRIOR"},
            "elo_rating":            {"value": r[7], "type": "COMPUTED"},
            "data_source": r[8], "snapshot_date": str(r[9]),
        })

    computed_teams = sum(1 for t in teams_audit if t["form_score"]["type"] == "COMPUTED")
    return {
        "classification": FEATURE_CLASSIFICATION,
        "teams": teams_audit,
        "summary": {
            "total_teams": len(teams_audit),
            "computed_form": computed_teams,
            "prior_form_only": len(teams_audit) - computed_teams,
            "note": "form_score ist COMPUTED sobald WM-Ergebnisse vorliegen, sonst 0.0",
        },
    }
