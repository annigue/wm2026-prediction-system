"""Prediction Engine: orchestriert Elo, Feature-Adjustment und Poisson."""

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings, HOST_NATIONS
from app.models.team import Team, TeamFeature
from app.models.match import Match, Venue, MatchResult
from app.models.prediction import MatchPrediction
from app.services.elo_model import EloModel
from app.services.poisson_model import PoissonModel
from app.services.feature_adjuster import FeatureAdjuster

_elo      = EloModel()
_poisson  = PoissonModel()
_adjuster = FeatureAdjuster()


def _host_bonus(stage, home_team_id, away_team_id) -> tuple[float, float]:
    """Gastgeber-Heimvorteil als gerichteter Elo-Bonus — NUR in der Gruppenphase
    (Gastgeber spielen dort im eigenen Land; KO-Austragungsort ist unklar → neutral).
    Bei Gastgeber-gegen-Gastgeber heben sich die Boni auf (beide +Bonus)."""
    if stage != "GROUP_STAGE":
        return 0.0, 0.0
    b = settings.host_advantage_elo
    return (b if home_team_id in HOST_NATIONS else 0.0,
            b if away_team_id in HOST_NATIONS else 0.0)


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


async def predict_match(match_id: str, db: AsyncSession, model_version: str = "v1.0",
                        blend_w: float | None = None) -> dict | None:
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

    # Gastgeber-Heimvorteil (gerichtet, nur Gruppenphase) ON TOP der Feature-Adjustierung
    host_home, host_away = _host_bonus(match.stage, match.home_team_id, match.away_team_id)
    eff_home_elo = adj.adjusted_home_elo + host_home
    eff_away_elo = adj.adjusted_away_elo + host_away

    # Attack-/Defense-Ratings (≈1.0 neutral) modulieren λ gedämpft (ad_gamma); Elo bleibt dominant.
    atk_h = (getattr(home_feat, "attack_rating", None) or 1.0)
    def_h = (getattr(home_feat, "defense_rating", None) or 1.0)
    atk_a = (getattr(away_feat, "attack_rating", None) or 1.0)
    def_a = (getattr(away_feat, "defense_rating", None) or 1.0)
    result = _poisson.predict(eff_home_elo, eff_away_elo,
                              atk_h, def_h, atk_a, def_a, settings.ad_gamma)

    factors = [
        {
            "name": f.name, "value": f.description, "elo_delta": f.elo_delta,
            "weight": f.weight,
            "direction": "home" if f.elo_delta > 0 else ("away" if f.elo_delta < 0 else "neutral"),
        }
        for f in adj.factors
    ]
    if host_home or host_away:
        net = host_home - host_away
        host_name = (home.name if host_home else away.name)
        factors.append({
            "name": "Gastgeber-Heimvorteil",
            "value": f"{host_name}: +{settings.host_advantage_elo:.0f} Elo (Gruppenphase im eigenen Land)",
            "elo_delta": round(net, 1), "weight": 1.0,
            "direction": "home" if net > 0 else "away",
        })

    explanation = {
        "summary":     adj.summary,
        "elo_home":    home_elo,
        "elo_away":    away_elo,
        "elo_delta":   round(home_elo - away_elo, 1),
        "feature_delta": adj.total_delta,
        "adjusted_elo_home": round(eff_home_elo, 1),
        "adjusted_elo_away": round(eff_away_elo, 1),
        "factors": factors,
    }

    if settings.ad_gamma > 0:
        explanation["attack_defense"] = {
            "gamma": settings.ad_gamma,
            "home": {"attack": round(atk_h, 3), "defense": round(def_h, 3)},
            "away": {"attack": round(atk_a, 3), "defense": round(def_a, 3)},
        }

    # Offizielle, markt-kalibrierte Prognose (Variante D + log-Blend).
    # Das reine Modell (result.* / top-level prob_*) bleibt für die Betting Engine unverändert.
    market_probs = None
    try:
        from app.services.odds_aggregator import get_market_probabilities
        mkt = get_market_probabilities(home.home_country or home.name,
                                       away.home_country or away.name)
        if mkt and mkt.get("fair_1x2"):
            f = mkt["fair_1x2"]
            market_probs = [f["home"], f["draw"], f["away"]]
    except Exception:
        market_probs = None  # Markt best-effort: darf die Prognose nie brechen

    from app.services.forecast_service import build_official_forecast
    explanation["official"] = build_official_forecast(
        [result.prob_home_win, result.prob_draw, result.prob_away_win],
        result.score_distribution,
        market_probs,
        w=blend_w,
    )

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


_blend_w_cache: tuple[float, float] | None = None  # (weight, timestamp)
_BLEND_W_TTL = 1800  # 30 Minuten Cache


def _compute_blend_weight() -> float | None:
    """Berechnet adaptives Markt-Gewicht (sync, gecacht für 30 Min).
    Gibt None zurück wenn adaptive_blend deaktiviert → forecast_service nutzt Default."""
    import time
    global _blend_w_cache

    if not settings.adaptive_blend:
        return None
    if _blend_w_cache and time.time() - _blend_w_cache[1] < _BLEND_W_TTL:
        return _blend_w_cache[0]
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.services.market_calibration_service import compute_adaptive_weight
        engine = create_engine(settings.database_url_sync)
        Session = sessionmaker(bind=engine)
        with Session() as session:
            w, _meta = compute_adaptive_weight(session)
        engine.dispose()
        _blend_w_cache = (w, time.time())
        return w
    except Exception:
        return None


async def predict_all_scheduled(db: AsyncSession, model_version: str = "v1.0") -> int:
    """Berechnet Prognosen für alle Spiele mit bekannten Teams (stage-agnostisch)."""
    blend_w = _compute_blend_weight()

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
        if await predict_match(mid, db, model_version, blend_w=blend_w):
            count += 1
    await db.commit()
    return count
