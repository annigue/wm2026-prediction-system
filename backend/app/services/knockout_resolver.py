"""
Knockout Resolver — schreibt die qualifizierten Teams in die KO-Spiel-Zeilen.

Variante A (self-contained, aus echten Ergebnissen):
  1. R32: sobald die Gruppenphase KOMPLETT gespielt ist → Gruppensieger/-zweite/8 beste
     Dritte aus den REALEN Tabellen in die ROUND_OF_32-Spiele schreiben.
  2. R16/VF/HF/Finale/Platz3: inkrementell aus REALEN KO-Ergebnissen (sobald beide
     Zubringer-Spiele ein Ergebnis haben).

Deterministisch & idempotent. KEIN Eingriff in Elo/Poisson/Simulation. Schreibt nur
matches.home/away_team_id. Danach erzeugt predict_all_scheduled die Prognosen.

Limitation: KO-Spiel im Elfmeterschießen → Sieger nicht aus dem Torergebnis ableitbar;
Fallback höheres aktuelles Elo (wie Simulation/Projektion).
"""

from __future__ import annotations
from sqlalchemy import text
from sqlalchemy.orm import Session

# Spiel k einer Stage wird gespeist von den Spielen 2k-1 und 2k der vorherigen Stage.
KO_SEQUENCE = ["ROUND_OF_32", "ROUND_OF_16", "QUARTERFINAL", "SEMIFINAL", "FINAL"]


def _latest_elos(session: Session) -> dict[str, float]:
    rows = session.execute(text("""
        SELECT DISTINCT ON (t.id) t.id, tf.elo_rating
        FROM teams t JOIN team_features tf ON tf.team_id = t.id
        ORDER BY t.id, tf.snapshot_date DESC
    """)).fetchall()
    return {r[0]: float(r[1] or 1500) for r in rows}


def _ko_match_ids(session: Session, stage: str) -> list[str]:
    rows = session.execute(text(
        "SELECT id FROM matches WHERE stage = :s ORDER BY id"
    ), {"s": stage}).fetchall()
    return [r[0] for r in rows]


def _group_stage_complete(session: Session) -> bool:
    row = session.execute(text("""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE EXISTS (
                   SELECT 1 FROM match_results mr WHERE mr.match_id = m.id)) AS played
        FROM matches m WHERE m.stage = 'GROUP_STAGE'
    """)).fetchone()
    return row[0] > 0 and row[0] == row[1]


def _compute_r32_pairs(session: Session, elos: dict[str, float]) -> list[tuple[str, str]]:
    """Reale Gruppentabellen → R32-Paarungen (kanonische Logik aus tournament_projection)."""
    from app.services.tournament_projection import rank_and_pair

    grp_rows = session.execute(text(
        "SELECT group_id, team_id FROM group_memberships ORDER BY group_id"
    )).fetchall()
    groups: dict[str, list[str]] = {}
    for gid, tid in grp_rows:
        groups.setdefault(gid, []).append(tid)

    standings = {gid: {t: {"pts": 0, "gf": 0, "ga": 0} for t in teams}
                 for gid, teams in groups.items()}

    res_rows = session.execute(text("""
        SELECT m.group_id, m.home_team_id, m.away_team_id, mr.home_goals, mr.away_goals
        FROM   matches m JOIN match_results mr ON mr.match_id = m.id
        WHERE  m.stage = 'GROUP_STAGE'
          AND  m.home_team_id IS NOT NULL AND m.away_team_id IS NOT NULL
    """)).fetchall()
    for gid, hid, aid, sh, sa in res_rows:
        if gid not in standings:
            continue
        sh, sa = int(sh), int(sa)
        standings[gid][hid]["pts"] += 3 if sh > sa else (1 if sh == sa else 0)
        standings[gid][aid]["pts"] += 3 if sa > sh else (1 if sh == sa else 0)
        standings[gid][hid]["gf"] += sh; standings[gid][hid]["ga"] += sa
        standings[gid][aid]["gf"] += sa; standings[gid][aid]["ga"] += sh

    return rank_and_pair(standings, elos)["r32_pairs"]


def _set_match_teams(session: Session, match_id: str,
                     home_id: str | None, away_id: str | None) -> bool:
    cur = session.execute(text(
        "SELECT home_team_id, away_team_id FROM matches WHERE id = :id"
    ), {"id": match_id}).fetchone()
    if cur is None or (cur[0] == home_id and cur[1] == away_id):
        return False
    session.execute(text(
        "UPDATE matches SET home_team_id = :h, away_team_id = :a WHERE id = :id"
    ), {"h": home_id, "a": away_id, "id": match_id})
    return True


def _feeder_winner(session: Session, match_id: str, elos: dict[str, float]) -> str | None:
    row = session.execute(text("""
        SELECT m.home_team_id, m.away_team_id, mr.home_goals, mr.away_goals
        FROM   matches m JOIN match_results mr ON mr.match_id = m.id
        WHERE  m.id = :id
    """), {"id": match_id}).fetchone()
    if not row or row[0] is None or row[1] is None:
        return None
    hid, aid, sh, sa = row[0], row[1], int(row[2]), int(row[3])
    if sh > sa:
        return hid
    if sa > sh:
        return aid
    return hid if elos.get(hid, 1500) >= elos.get(aid, 1500) else aid


def resolve_bracket(session: Session) -> dict:
    """Befüllt die KO-Spiele so weit wie aus realen Ergebnissen möglich (committet NICHT)."""
    elos = _latest_elos(session)
    changed = 0
    stages_done: list[str] = []

    if not _group_stage_complete(session):
        return {"filled": 0, "reason": "Gruppenphase noch nicht vollständig gespielt",
                "stages_resolved": []}

    r32_ids = _ko_match_ids(session, "ROUND_OF_32")
    pairs = _compute_r32_pairs(session, elos)
    if len(pairs) == len(r32_ids) and pairs:
        for mid, (hid, aid) in zip(r32_ids, pairs):
            if _set_match_teams(session, mid, hid, aid):
                changed += 1
        stages_done.append("ROUND_OF_32")

    for prev_stage, stage in zip(KO_SEQUENCE[:-1], KO_SEQUENCE[1:]):
        prev_ids = _ko_match_ids(session, prev_stage)
        stage_ids = _ko_match_ids(session, stage)
        resolved_here = 0
        for k, mid in enumerate(stage_ids):
            f1, f2 = 2 * k, 2 * k + 1
            if f2 >= len(prev_ids):
                break
            w1 = _feeder_winner(session, prev_ids[f1], elos)
            w2 = _feeder_winner(session, prev_ids[f2], elos)
            if w1 and w2:
                if _set_match_teams(session, mid, w1, w2):
                    changed += 1
                resolved_here += 1
        if resolved_here:
            stages_done.append(stage)

    third_ids = _ko_match_ids(session, "THIRD_PLACE")
    sf_ids = _ko_match_ids(session, "SEMIFINAL")
    if third_ids and len(sf_ids) == 2:
        losers = []
        for sf in sf_ids:
            w = _feeder_winner(session, sf, elos)
            row = session.execute(text(
                "SELECT home_team_id, away_team_id FROM matches WHERE id = :id"
            ), {"id": sf}).fetchone()
            if w and row and row[0] and row[1]:
                losers.append(row[1] if w == row[0] else row[0])
        if len(losers) == 2:
            if _set_match_teams(session, third_ids[0], losers[0], losers[1]):
                changed += 1
            stages_done.append("THIRD_PLACE")

    return {"filled": changed, "stages_resolved": stages_done,
            "reason": "ok" if changed else "keine neuen Paarungen bestimmbar"}
