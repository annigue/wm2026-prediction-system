"""Prediction Engine: orchestriert Elo, Feature-Adjustment und Poisson."""

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team, TeamFeature
from app.models.match import Match, Venue, MatchResult
from app.models.prediction import MatchPrediction
from app.services.elo_model import EloModel
from app.services.poisson_model import PoissonModel
from app.services.feature_adjuster import FeatureAdjuster

_elo      = EloModel()
_poisson  = PoissonModel()
_adjuster = FeatureAdjuster()


async def _rest_days(team_id: str, kickoff, db: AsyncSession) -> float | None:
    """Tage seit dem letzten TATSÄCHLICH GESPIELTEN Spiel des Teams vor `kickoff`.

    Nur Spiele mit echtem Ergebnis (JOIN match_results) zählen — Fatigue entsteht nur
    durch gespielte Spiele (verhindert Phantom-Fatigue vor Turnierstart). None = neutral.
    """
    if not kickoff:
        return None
    from sqlalchemy import or_
    q = await db.execute(
        select(Match.kickoff_utc)
        .join(MatchResult, MatchResult.match_id == Match.id)
        .where(
            or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
            Match.kickoff_utc < kickoff,
        )
        .order_by(Match.kickoff_utc.desc())
        .limit(1)
    )
    prev = q.scalar_one_or_none()
    if prev is None:
        return None
    return round((kickoff - prev).total_seconds() / 86400.0, 2)


def _features_snapshot(feat) -> dict | None:
    if not feat:
        return None
    return {
        "elo_rating":             feat.elo_rating,
        "fifa_ranking":           feat.fifa_ranking,
        "market_value_millions":  feat.market_value_millions,
        "avg_squad_age":          feat.avg_squad_age,
        "avg_caps_per_player":    feat.avg_caps_per_player,
        "form_score":             feat.form_score,
    }


async def predict_match(match_id: str, db: AsyncSession, model_version: str = "v1.0") -> dict | None:
    """Berechnet Prognose für ein Spiel, speichert und gibt dict zurück."""
    q = await db.execute(
        select(Match)
        .options(
            selectinload(Match.home_team).selectinload(Team.features),
            selectinload(Match.away_team).selectinload(Team.features),
            selectinload(Match.venue),
            selectinload(Match.predictions),
        )
        .where(Match.id == match_id)
    )
    match = q.scalar_one_or_none()
    if not match or not match.home_team_id or not match.away_team_id:
        return None

    home, away, venue = match.home_team, match.away_team, match.venue
    home_feat = home.features[0] if home and home.features else None
    away_feat = away.features[0] if away and away.features else None

    home_elo = (home_feat.elo_rating if home_feat else 1500.0) or 1500.0
    away_elo = (away_feat.elo_rating if away_feat else 1500.0) or 1500.0

    rest_home = await _rest_days(match.home_team_id, match.kickoff_utc, db)
    rest_away = await _rest_days(match.away_team_id, match.kickoff_utc, db)

    adj = _adjuster.adjust(home, away, home_feat, away_feat, venue,
                           rest_home=rest_home, rest_away=rest_away)
    result = _poisson.predict(adj.adjusted_home_elo, adj.adjusted_away_elo)

    explanation = {
        "summary":     adj.summary,
        "elo_home":    home_elo,
        "elo_away":    away_elo,
        "elo_delta":   round(home_elo - away_elo, 1),
        "feature_delta": adj.total_delta,
        "adjusted_elo_home": adj.adjusted_home_elo,
        "adjusted_elo_away": adj.adjusted_away_elo,
        "factors": [
            {
                "name": f.name, "value": f.description, "elo_delta": f.elo_delta,
                "weight": f.weight,
                "direction": "home" if f.elo_delta > 0 else ("away" if f.elo_delta < 0 else "neutral"),
            }
            for f in adj.factors
        ],
    }

    existing = next((p for p in match.predictions if p.model_version == model_version), None)
    pred = existing or MatchPrediction(match_id=match_id, model_version=model_version)
    if existing is None:
        db.add(pred)

    pred.prob_home_win          = result.prob_home_win
    pred.prob_draw              = result.prob_draw
    pred.prob_away_win          = result.prob_away_win
    pred.xg_home                = result.lambda_home
    pred.xg_away                = result.lambda_away
    pred.top_scorelines         = result.top_scorelines
    pred.score_distribution     = result.score_distribution
    pred.explanation            = explanation
    pred.home_elo_at_prediction = home_elo
    pred.away_elo_at_prediction = away_elo
    pred.home_features_snapshot = _features_snapshot(home_feat)
    pred.away_features_snapshot = _features_snapshot(away_feat)
    pred.predicted_at           = datetime.utcnow()

    await db.flush()

    return {
        "match_id": match_id, "model_version": model_version,
        "home_team": home.name if home else "?", "away_team": away.name if away else "?",
        "prob_home_win": result.prob_home_win, "prob_draw": result.prob_draw,
        "prob_away_win": result.prob_away_win,
        "xg_home": result.lambda_home, "xg_away": result.lambda_away,
        "top_scorelines": result.top_scorelines, "explanation": explanation,
    }


async def predict_all_scheduled(db: AsyncSession, model_version: str = "v1.0") -> int:
    """Berechnet Prognosen für alle Spiele mit bekannten Teams (stage-agnostisch)."""
    q = await db.execute(
        select(Match.id)
        .where(
            Match.status.in_(["SCHEDULED", "LIVE"]),
            Match.home_team_id.isnot(None),
            Match.away_team_id.isnot(None),
        )
        .order_by(Match.kickoff_utc)
    )
    ids = [row[0] for row in q.fetchall()]
    count = 0
    for mid in ids:
        if await predict_match(mid, db, model_version):
            count += 1
    await db.commit()
    return count
