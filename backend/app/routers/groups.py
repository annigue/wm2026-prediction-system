from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, text
from sqlalchemy.orm import noload

from app.database import get_db
from app.models.team import Group, Team
from app.models.simulation import TournamentSimulation
from app.schemas.simulation import GroupOut, GroupStandingEntry

router = APIRouter()


@router.get("/")
async def list_groups(db: AsyncSession = Depends(get_db)):
    # Letzte Simulation für Qualifikations-Wahrscheinlichkeiten
    sim = (await db.execute(
        select(TournamentSimulation).order_by(desc(TournamentSimulation.simulated_at)).limit(1)
    )).scalar_one_or_none()
    stage_probs = sim.stage_probs if sim else {}

    grp_rows = (await db.execute(text(
        "SELECT group_id, team_id FROM group_memberships ORDER BY group_id"))).fetchall()
    members: dict[str, list[str]] = {}
    for gid, tid in grp_rows:
        members.setdefault(gid, []).append(tid)

    teams = {t.id: t for t in (await db.execute(select(Team).options(
        noload(Team.features), noload(Team.elo_history), noload(Team.groups)))).scalars().all()}

    # Tabellen aus realen Ergebnissen
    res_rows = (await db.execute(text("""
        SELECT m.group_id, m.home_team_id, m.away_team_id, mr.home_goals, mr.away_goals
        FROM matches m JOIN match_results mr ON mr.match_id = m.id
        WHERE m.stage = 'GROUP_STAGE'
    """))).fetchall()

    stand: dict[str, dict] = {gid: {t: dict(p=0, w=0, d=0, l=0, gf=0, ga=0) for t in ts}
                              for gid, ts in members.items()}
    for gid, hid, aid, sh, sa in res_rows:
        if gid not in stand:
            continue
        sh, sa = int(sh), int(sa)
        for tid, gf, ga in ((hid, sh, sa), (aid, sa, sh)):
            s = stand[gid][tid]
            s["gf"] += gf; s["ga"] += ga
            if gf > ga: s["w"] += 1; s["p"] += 3
            elif gf == ga: s["d"] += 1; s["p"] += 1
            else: s["l"] += 1

    groups_db = {g.id: g for g in (await db.execute(select(Group))).scalars().all()}
    out = []
    for gid in sorted(members):
        entries = []
        for tid in members[gid]:
            s = stand[gid][tid]
            t = teams.get(tid)
            qp = (stage_probs.get(tid, {}) or {}).get("round_of_32")
            wp = (stage_probs.get(tid, {}) or {}).get("group_winner")
            entries.append(GroupStandingEntry(
                team_id=tid, team_name=t.name if t else tid,
                flag_emoji=t.flag_emoji if t else None,
                played=s["w"] + s["d"] + s["l"], won=s["w"], drawn=s["d"], lost=s["l"],
                goals_for=s["gf"], goals_against=s["ga"], points=s["p"],
                qualification_probability=qp, win_group_probability=wp,
            ))
        entries.sort(key=lambda e: (e.points, e.goals_for - e.goals_against, e.goals_for),
                     reverse=True)
        g = groups_db.get(gid)
        out.append(GroupOut(id=gid, name=g.name if g else f"Gruppe {gid}", teams=entries))
    return {"groups": out}
