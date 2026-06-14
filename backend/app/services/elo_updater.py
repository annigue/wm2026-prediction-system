"""
Elo-Update nach realem Spielergebnis (klassisches Elo, keine Bayes-Inferenz).

Nach jedem Ergebnis:
1. Neue Elo-Werte berechnen (K=20 während Turnier — konservativ)
2. Audit-Trail in elo_ratings speichern
3. team_features.elo_rating für beide Teams aktualisieren
"""

from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import TeamFeature, EloRating
from app.services.elo_model import EloModel

# K-Faktor während des Turniers: konservativer als reguläre Länderspiele (K=32)
K_TOURNAMENT = 20.0


async def _latest_feature(team_id: str, db: AsyncSession) -> TeamFeature | None:
    q = await db.execute(
        select(TeamFeature)
        .where(TeamFeature.team_id == team_id)
        .order_by(TeamFeature.snapshot_date.desc())
        .limit(1)
    )
    return q.scalar_one_or_none()


async def apply_result(
    match_id: str,
    home_team_id: str,
    away_team_id: str,
    home_goals: int,
    away_goals: int,
    db: AsyncSession,
) -> dict:
    """Aktualisiert Elo beider Teams nach einem Spielergebnis."""
    home_feat = await _latest_feature(home_team_id, db)
    away_feat = await _latest_feature(away_team_id, db)

    home_elo_before = (home_feat.elo_rating if home_feat else 1500.0) or 1500.0
    away_elo_before = (away_feat.elo_rating if away_feat else 1500.0) or 1500.0

    new_home_elo, new_away_elo = EloModel.update_both(
        home_elo_before, away_elo_before,
        home_goals, away_goals,
        k=K_TOURNAMENT,
    )

    reason = f"WM2026 {home_goals}:{away_goals}"

    db.add(EloRating(team_id=home_team_id, rating=new_home_elo, match_id=match_id, reason=reason))
    db.add(EloRating(team_id=away_team_id, rating=new_away_elo, match_id=match_id, reason=reason))

    if home_feat:
        home_feat.elo_rating = new_home_elo
    else:
        db.add(TeamFeature(team_id=home_team_id, snapshot_date=date.today(),
                           elo_rating=new_home_elo, data_source="elo_update"))

    if away_feat:
        away_feat.elo_rating = new_away_elo
    else:
        db.add(TeamFeature(team_id=away_team_id, snapshot_date=date.today(),
                           elo_rating=new_away_elo, data_source="elo_update"))

    await db.flush()

    # WICHTIG: Die Form-Neuberechnung (Form Engine) läuft NICHT hier, sondern im
    # Hintergrund-Task NACH dem Commit (siehe matches._after_result_tasks) — sonst
    # Deadlock (Lock-Wait) auf team_features durch uncommittete Elo-Schreibzugriffe.

    return {
        home_team_id: {
            "before": round(home_elo_before, 1),
            "after":  round(new_home_elo, 1),
            "delta":  round(new_home_elo - home_elo_before, 1),
        },
        away_team_id: {
            "before": round(away_elo_before, 1),
            "after":  round(new_away_elo, 1),
            "delta":  round(new_away_elo - away_elo_before, 1),
        },
    }
