from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.config import settings
from app.models.match import Match, MatchResult
from app.schemas.match import (
    MatchSummary, MatchDetail, PredictionSummary, PredictionDetail, ResultOut, ResultCreate,
    VenueOut,
)
from app.schemas.team import TeamSummary

router = APIRouter()


def _team_summary(team) -> Optional[TeamSummary]:
    if not team:
        return None
    f = team.features[0] if getattr(team, "features", None) else None
    return TeamSummary(
        id=team.id, name=team.name, short_name=team.short_name,
        flag_emoji=team.flag_emoji, confederation=team.confederation,
        elo_rating=f.elo_rating if f else None,
        form_score=f.form_score if f else None,
    )


def _latest_prediction(match):
    if not match.predictions:
        return None
    return sorted(match.predictions, key=lambda p: p.predicted_at, reverse=True)[0]


def _pred_summary(pred) -> Optional[PredictionSummary]:
    if not pred:
        return None
    top = pred.top_scorelines[0]["score"] if pred.top_scorelines else None
    return PredictionSummary(
        prob_home_win=pred.prob_home_win, prob_draw=pred.prob_draw,
        prob_away_win=pred.prob_away_win, xg_home=pred.xg_home, xg_away=pred.xg_away,
        model_version=pred.model_version, top_scoreline=top,
    )


def _build_match_summary(match) -> MatchSummary:
    return MatchSummary(
        id=match.id, stage=match.stage, group_id=match.group_id,
        home_team=_team_summary(match.home_team), away_team=_team_summary(match.away_team),
        kickoff_utc=match.kickoff_utc, status=match.status,
        prediction=_pred_summary(_latest_prediction(match)),
        result=ResultOut.model_validate(match.result) if match.result else None,
    )


_SUMMARY_OPTS = [
    selectinload(Match.home_team), selectinload(Match.away_team),
    selectinload(Match.predictions), selectinload(Match.result),
]


@router.get("/")
async def list_matches(
    stage: Optional[str] = Query(None), group_id: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None), status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Match).options(*_SUMMARY_OPTS).order_by(Match.kickoff_utc)
    if stage:
        stmt = stmt.where(Match.stage == stage)
    if group_id:
        stmt = stmt.where(Match.group_id == group_id)
    if status:
        stmt = stmt.where(Match.status == status)
    if team_id:
        stmt = stmt.where((Match.home_team_id == team_id) | (Match.away_team_id == team_id))
    matches = (await db.execute(stmt)).scalars().all()
    return {"matches": [_build_match_summary(m) for m in matches]}


@router.get("/{match_id}", response_model=MatchDetail)
async def get_match(match_id: str, db: AsyncSession = Depends(get_db)):
    q = await db.execute(
        select(Match).options(*_SUMMARY_OPTS, selectinload(Match.venue)).where(Match.id == match_id)
    )
    match = q.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Spiel nicht gefunden")
    pred = _latest_prediction(match)
    detail = MatchDetail(
        id=match.id, stage=match.stage, group_id=match.group_id,
        home_team=_team_summary(match.home_team), away_team=_team_summary(match.away_team),
        kickoff_utc=match.kickoff_utc, status=match.status,
        result=ResultOut.model_validate(match.result) if match.result else None,
        venue=VenueOut.model_validate(match.venue) if match.venue else None,
        prediction=PredictionDetail.model_validate(pred) if pred else None,
    )
    if detail.prediction and pred and pred.top_scorelines:
        detail.prediction.top_scoreline = pred.top_scorelines[0]["score"]
    return detail


@router.get("/{match_id}/bets", response_model=dict)
async def get_match_bets(
    match_id: str,
    home_odds: Optional[float] = Query(None), draw_odds: Optional[float] = Query(None),
    away_odds: Optional[float] = Query(None), over25_odds: Optional[float] = Query(None),
    under25_odds: Optional[float] = Query(None), btts_yes_odds: Optional[float] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    from app.services.decision_engine import generate_recommendations, report_to_dict
    odds = {}
    if home_odds:    odds["1X2:HOME"] = home_odds
    if draw_odds:    odds["1X2:DRAW"] = draw_odds
    if away_odds:    odds["1X2:AWAY"] = away_odds
    if over25_odds:  odds["OVER_UNDER_2.5:OVER"] = over25_odds
    if under25_odds: odds["OVER_UNDER_2.5:UNDER"] = under25_odds
    if btts_yes_odds: odds["BTTS:YES"] = btts_yes_odds
    report = await generate_recommendations(match_id, db, odds or None)
    if not report:
        raise HTTPException(status_code=404, detail="Spiel/Prognose nicht gefunden")
    return report_to_dict(report)


@router.get("/{match_id}/tip", response_model=dict)
async def get_match_tip(match_id: str, db: AsyncSession = Depends(get_db)):
    from app.services.tipping_engine import generate_tip_for_match
    tip = await generate_tip_for_match(match_id, db)
    if not tip:
        raise HTTPException(status_code=404, detail="Keine Prognose vorhanden")
    return tip


@router.post("/{match_id}/result", response_model=dict)
async def record_result(
    match_id: str, body: ResultCreate, background_tasks: BackgroundTasks,
    authorization: str = Header(...), db: AsyncSession = Depends(get_db),
):
    if (authorization or "").replace("Bearer ", "").strip() != settings.admin_token:
        raise HTTPException(status_code=401, detail="Ungültiges Admin-Token")

    from app.services.bayesian_updater import apply_result

    q = await db.execute(select(Match).where(Match.id == match_id))
    match = q.scalar_one_or_none()
    if not match or not match.home_team_id or not match.away_team_id:
        raise HTTPException(status_code=404, detail="Spiel/Teams nicht gefunden")

    existing = (await db.execute(
        select(MatchResult).where(MatchResult.match_id == match_id))).scalar_one_or_none()
    if existing:
        existing.home_goals = body.home_goals
        existing.away_goals = body.away_goals
        existing.went_to_extra_time = body.went_to_extra_time
        existing.went_to_penalties = body.went_to_penalties
    else:
        db.add(MatchResult(
            match_id=match_id, home_goals=body.home_goals, away_goals=body.away_goals,
            went_to_extra_time=body.went_to_extra_time, went_to_penalties=body.went_to_penalties,
            source="manual",
        ))
    match.status = "FINISHED"

    elo_updates = await apply_result(
        match_id=match_id, home_team_id=match.home_team_id, away_team_id=match.away_team_id,
        home_goals=body.home_goals, away_goals=body.away_goals, db=db,
    )
    await db.commit()
    background_tasks.add_task(_after_result_tasks, match_id)

    return {
        "status": "accepted", "match_id": match_id,
        "result": f"{body.home_goals}:{body.away_goals}", "elo_updates": elo_updates,
        "message": "Ergebnis gespeichert. Elo aktualisiert. Prognosen + Simulation laufen im Hintergrund.",
    }


def _after_result_tasks(match_id: str):
    """Hintergrund: Form → KO-Bracket → Prognosen → Cache → Simulation."""
    import asyncio
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import AsyncSessionLocal
    from app.services.prediction_engine import predict_all_scheduled
    from app.services.form_engine import update_all_forms
    from app.services.knockout_resolver import resolve_bracket

    sync_engine = create_engine(settings.database_url_sync)
    SyncSession = sessionmaker(bind=sync_engine)
    with SyncSession() as s:
        update_all_forms(s)
        resolve_bracket(s)
        s.commit()
    sync_engine.dispose()

    async def _run():
        async with AsyncSessionLocal() as db:
            await predict_all_scheduled(db)
            await db.commit()
    asyncio.run(_run())

    from app.services.cache import invalidate
    invalidate("wm2026:")

    from app.routers.admin import _simulation_task
    _simulation_task()
