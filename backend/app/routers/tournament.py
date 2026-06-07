from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.team import Team
from app.models.simulation import TournamentSimulation

router = APIRouter()


async def _latest(db: AsyncSession) -> TournamentSimulation | None:
    return (await db.execute(
        select(TournamentSimulation).order_by(desc(TournamentSimulation.simulated_at)).limit(1)
    )).scalar_one_or_none()


def _sim_result(sim) -> dict:
    """SimulationResult-Shape (Frontend-Contract): champion_probabilities / stage_probabilities."""
    if not sim:
        return {"champion_probabilities": {}, "stage_probabilities": {}}
    return {
        "simulation_id": sim.id,
        "n_runs": sim.n_runs,
        "model_version": sim.model_version,
        "simulated_at": sim.simulated_at.isoformat(),
        "champion_probabilities": sim.champion_probs or {},
        "stage_probabilities": sim.stage_probs or {},
    }


@router.get("/")
async def get_simulation_root(db: AsyncSession = Depends(get_db)):
    return _sim_result(await _latest(db))


@router.get("/simulate")
async def get_simulation(db: AsyncSession = Depends(get_db)):
    """Neueste Simulation (SimulationResult). (Auslösen: POST /admin/simulate.)"""
    return _sim_result(await _latest(db))


@router.get("/champion-probabilities")
async def champion_probabilities(db: AsyncSession = Depends(get_db)):
    sim = await _latest(db)
    return {"champion_probabilities": (sim.champion_probs if sim else {}) or {}}


@router.get("/projection")
async def projection(db: AsyncSession = Depends(get_db)):
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.config import settings
    from app.services.tournament_projection import build_projection
    from app.services.cache import cached

    def _produce():
        engine = create_engine(settings.database_url_sync)
        Session = sessionmaker(bind=engine)
        with Session() as s:
            proj = build_projection(s)
        engine.dispose()
        return proj

    return cached("wm2026:projection", 1800, _produce)


@router.get("/bets")
async def tournament_bets(
    stage: str = Query("GROUP_STAGE"), min_ev: float = Query(0.02),
    limit: int = Query(20), db: AsyncSession = Depends(get_db),
):
    from app.models.match import Match
    from app.services.decision_engine import generate_recommendations

    ids = [r[0] for r in (await db.execute(
        select(Match.id).where(Match.stage == stage, Match.status.in_(["SCHEDULED", "LIVE"]),
                               Match.home_team_id.isnot(None)).order_by(Match.kickoff_utc)
    )).fetchall()]

    best_bets = []
    for mid in ids:
        report = await generate_recommendations(mid, db)
        if report and report.best_bet and report.best_bet.ev >= min_ev:
            bb = report.best_bet
            best_bets.append({
                "match_id": mid, "home_team": report.home_name, "away_team": report.away_name,
                "selection": bb.selection, "ev": bb.ev, "ev_label": bb.ev_label,
                "edge": bb.edge, "odds": bb.odds, "recommendation": bb.recommendation,
                "scoreline": report.scoreline_tip,
            })
    best_bets.sort(key=lambda b: b["ev"], reverse=True)
    return {"stage": stage, "count": len(best_bets), "best_bets": best_bets[:limit]}
