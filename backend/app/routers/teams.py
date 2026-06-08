from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload, noload

from app.database import get_db
from app.models.team import Team
from app.models.simulation import TournamentSimulation
from app.schemas.team import (
    TeamSummary, TeamDetail, TeamFeatureOut, EloRatingOut, TournamentProbsOut,
)

router = APIRouter()


async def _latest_sim(db: AsyncSession) -> TournamentSimulation | None:
    q = await db.execute(
        select(TournamentSimulation).order_by(desc(TournamentSimulation.simulated_at)).limit(1)
    )
    return q.scalar_one_or_none()


def _team_to_summary(team: Team, champion_prob=None) -> TeamSummary | None:
    f = team.features[0] if team.features else None
    return TeamSummary(
        id=team.id, name=team.name, short_name=team.short_name,
        flag_emoji=team.flag_emoji, confederation=team.confederation,
        elo_rating=f.elo_rating if f else None,
        fifa_ranking=f.fifa_ranking if f else None,
        market_value_millions=f.market_value_millions if f else None,
        avg_squad_age=f.avg_squad_age if f else None,
        form_score=f.form_score if f else None,
        champion_probability=champion_prob,
    )


@router.get("/")
async def list_teams(db: AsyncSession = Depends(get_db)):
    sim = await _latest_sim(db)
    champ = sim.champion_probs if sim else {}
    q = await db.execute(select(Team).options(
        selectinload(Team.features), noload(Team.elo_history), noload(Team.groups)))
    teams = q.scalars().all()
    out = [_team_to_summary(t, champ.get(t.id)) for t in teams]
    out.sort(key=lambda s: (s.champion_probability or 0, s.elo_rating or 0), reverse=True)
    return {"teams": out}


@router.get("/{team_id}", response_model=TeamDetail)
async def get_team(team_id: str, db: AsyncSession = Depends(get_db)):
    q = await db.execute(
        select(Team).options(
            selectinload(Team.features), selectinload(Team.elo_history),
            selectinload(Team.groups),
        ).where(Team.id == team_id)
    )
    team = q.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team nicht gefunden")

    sim = await _latest_sim(db)
    probs = None
    if sim and sim.stage_probs and team_id in sim.stage_probs:
        probs = TournamentProbsOut(**{k: v for k, v in sim.stage_probs[team_id].items()
                                      if k in TournamentProbsOut.model_fields})

    f = team.features[0] if team.features else None
    return TeamDetail(
        id=team.id, name=team.name, short_name=team.short_name,
        flag_emoji=team.flag_emoji, confederation=team.confederation,
        home_country=team.home_country,
        features=TeamFeatureOut.model_validate(f) if f else None,
        elo_history=[EloRatingOut.model_validate(e) for e in (team.elo_history or [])[:30]],
        tournament_probs=probs,
        group_id=team.groups[0].id if team.groups else None,
    )
