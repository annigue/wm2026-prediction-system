from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload, noload

from app.database import get_db
from app.models.match import Match
from app.models.team import Team
from app.models.simulation import TournamentSimulation

router = APIRouter()


def _utcnow_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _match_options():
    return [selectinload(Match.home_team), selectinload(Match.away_team), selectinload(Match.result)]


def _mini(match) -> dict:
    return {
        "id": match.id, "stage": match.stage, "group_id": match.group_id,
        "kickoff_utc": match.kickoff_utc.isoformat() if match.kickoff_utc else None,
        "status": match.status,
        "home_team": match.home_team.name if match.home_team else None,
        "home_flag": match.home_team.flag_emoji if match.home_team else None,
        "away_team": match.away_team.name if match.away_team else None,
        "away_flag": match.away_team.flag_emoji if match.away_team else None,
        "result": (f"{match.result.home_goals}:{match.result.away_goals}"
                   if match.result else None),
    }


@router.get("/")
async def dashboard(db: AsyncSession = Depends(get_db)):
    now = _utcnow_naive()

    sim = (await db.execute(
        select(TournamentSimulation).order_by(desc(TournamentSimulation.simulated_at)).limit(1)
    )).scalar_one_or_none()

    teams = {t.id: t for t in (await db.execute(select(Team).options(
        noload(Team.features), noload(Team.elo_history), noload(Team.groups)))).scalars().all()}
    top_favorites = []
    if sim and sim.champion_probs:
        ranked = sorted(sim.champion_probs.items(), key=lambda kv: kv[1], reverse=True)[:10]
    else:
        # Fallback ohne Simulation: nach Elo
        feats = (await db.execute(select(Team).options(
            selectinload(Team.features), noload(Team.elo_history), noload(Team.groups)))).scalars().all()
        ranked = sorted(
            [(t.id, (t.features[0].elo_rating if t.features else 1500)) for t in feats],
            key=lambda kv: kv[1], reverse=True)[:10]
        ranked = [(tid, 0.0) for tid, _ in ranked]
    for tid, p in ranked:
        t = teams.get(tid)
        top_favorites.append({
            "team_id": tid, "name": t.name if t else tid,
            "flag": t.flag_emoji if t else None, "champion_prob": round(p, 4),
        })

    # Turnier-Status
    total = (await db.execute(select(func.count()).select_from(Match))).scalar() or 0
    played = (await db.execute(
        select(func.count()).select_from(Match).where(Match.status == "FINISHED"))).scalar() or 0
    next_stage_row = (await db.execute(
        select(Match.stage).where(Match.status.in_(["SCHEDULED", "LIVE"]),
                                  Match.kickoff_utc.isnot(None))
        .order_by(Match.kickoff_utc).limit(1))).scalar_one_or_none()
    tournament_status = {
        "matches_played": played, "matches_total": total,
        "stage": next_stage_row or "GROUP_STAGE",
    }

    upcoming = (await db.execute(
        select(Match).options(*_match_options())
        .where(Match.status.in_(["SCHEDULED", "LIVE"]), Match.kickoff_utc >= now,
               Match.home_team_id.isnot(None))
        .order_by(Match.kickoff_utc).limit(8)
    )).scalars().all()

    recent = (await db.execute(
        select(Match).options(*_match_options())
        .where(Match.status == "FINISHED").order_by(desc(Match.kickoff_utc)).limit(8)
    )).scalars().all()

    return {
        "top_favorites": top_favorites,
        "tournament_status": tournament_status,
        "next_matches": [_mini(m) for m in upcoming],
        "recent_results": [_mini(m) for m in recent],
        "last_simulation": sim.simulated_at.isoformat() if sim else None,
    }
