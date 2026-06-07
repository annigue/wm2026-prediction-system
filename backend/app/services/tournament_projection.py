"""
Tournament Projection — deterministische Einzelprojektion (für Tippspiele).

Liefert EINEN plausibelsten Turnierverlauf (projiziertes Ergebnis je Spiel, Tabellen,
Qualifikanten, KO-Baum, Weltmeister). Reale Ergebnisse überschreiben die Projektion.
Deterministisch: gleiche Elo-Werte → gleiche Projektion.
"""

from __future__ import annotations
import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

BASE_GOALS = 1.30
ELO_SCALE  = 800.0
GROUP_ORDER = list("ABCDEFGHIJKL")


def rank_and_pair(standings: dict, elos: dict[str, float]) -> dict:
    """KANONISCHE Qualifikations- & R32-Paarungslogik (Single Source of Truth).

    standings: {gid: {team_id: {"pts","gf","ga"}}}. Genutzt von Projektion (projizierte
    Ergebnisse) UND knockout_resolver (reale Ergebnisse) — keine doppelte Bracket-Logik.
    Tie-Break: Punkte → Tordifferenz → Tore → Elo. R32: A1–B2, A2–B1, … + 8 beste Dritte.
    """
    winners, runners_up, thirds = {}, {}, []
    for gid, table in standings.items():
        ranked = sorted(
            table.items(),
            key=lambda kv: (kv[1]["pts"], kv[1]["gf"] - kv[1]["ga"],
                            kv[1]["gf"], elos.get(kv[0], 1500)),
            reverse=True,
        )
        winners[gid]    = ranked[0][0]
        runners_up[gid] = ranked[1][0]
        thirds.append((ranked[2][0], ranked[2][1]["pts"],
                       ranked[2][1]["gf"] - ranked[2][1]["ga"], ranked[2][1]["gf"]))

    thirds.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)
    best_thirds = [t[0] for t in thirds[:8]]

    pairs: list[tuple[str, str]] = []
    for i in range(0, 12, 2):
        gA, gB = GROUP_ORDER[i], GROUP_ORDER[i + 1]
        if gA in winners and gB in winners:
            pairs.append((winners[gA], runners_up[gB]))
            pairs.append((runners_up[gA], winners[gB]))
    for i in range(0, len(best_thirds) - 1, 2):
        pairs.append((best_thirds[i], best_thirds[i + 1]))

    return {"winners": winners, "runners_up": runners_up,
            "best_thirds": best_thirds, "r32_pairs": pairs}


def _projected_score(elo_h: float, elo_a: float) -> tuple[int, int]:
    diff = elo_h - elo_a
    lh = float(np.clip(BASE_GOALS * np.exp(diff / ELO_SCALE), 0.25, 5.0))
    la = float(np.clip(BASE_GOALS * np.exp(-diff / ELO_SCALE), 0.25, 5.0))
    return round(lh), round(la)


def _winner(elo_h: float, elo_a: float, hid: str, aid: str, sh: int, sa: int) -> str:
    if sh > sa:
        return hid
    if sa > sh:
        return aid
    return hid if elo_h >= elo_a else aid


def build_projection(session: Session) -> dict:
    """Erzeugt die vollständige deterministische Turnierprojektion."""
    elo_rows = session.execute(text("""
        SELECT DISTINCT ON (t.id) t.id, t.name, t.flag_emoji, tf.elo_rating
        FROM   teams t JOIN team_features tf ON tf.team_id = t.id
        ORDER  BY t.id, tf.snapshot_date DESC
    """)).fetchall()
    elos  = {r[0]: float(r[3] or 1500) for r in elo_rows}
    names = {r[0]: r[1] for r in elo_rows}
    flags = {r[0]: r[2] for r in elo_rows}

    grp_rows = session.execute(text(
        "SELECT group_id, team_id FROM group_memberships ORDER BY group_id"
    )).fetchall()
    groups: dict[str, list[str]] = {}
    for gid, tid in grp_rows:
        groups.setdefault(gid, []).append(tid)
    if not groups:
        return {"error": "Keine Gruppen vorhanden"}

    real_results = {}
    res_rows = session.execute(text("""
        SELECT m.id, m.home_team_id, m.away_team_id, mr.home_goals, mr.away_goals
        FROM   matches m JOIN match_results mr ON mr.match_id = m.id
        WHERE  m.stage = 'GROUP_STAGE'
    """)).fetchall()
    for r in res_rows:
        real_results[(r[1], r[2])] = (int(r[3]), int(r[4]))

    sched_rows = session.execute(text("""
        SELECT m.id, m.group_id, m.home_team_id, m.away_team_id, m.status, m.kickoff_utc
        FROM   matches m
        WHERE  m.stage = 'GROUP_STAGE'
          AND  m.home_team_id IS NOT NULL AND m.away_team_id IS NOT NULL
        ORDER  BY m.kickoff_utc
    """)).fetchall()

    standings = {gid: {t: {"pts": 0, "gf": 0, "ga": 0} for t in teams}
                 for gid, teams in groups.items()}
    projected_matches = []

    for row in sched_rows:
        mid, gid, hid, aid, status, kickoff = row
        if status == "FINISHED" and (hid, aid) in real_results:
            sh, sa = real_results[(hid, aid)]
            is_real = True
        else:
            sh, sa = _projected_score(elos.get(hid, 1500), elos.get(aid, 1500))
            is_real = False

        if gid in standings:
            standings[gid][hid]["pts"] += 3 if sh > sa else (1 if sh == sa else 0)
            standings[gid][aid]["pts"] += 3 if sa > sh else (1 if sh == sa else 0)
            standings[gid][hid]["gf"] += sh; standings[gid][hid]["ga"] += sa
            standings[gid][aid]["gf"] += sa; standings[gid][aid]["ga"] += sh

        projected_matches.append({
            "match_id": mid, "group": gid,
            "home": names.get(hid, hid), "away": names.get(aid, aid),
            "home_flag": flags.get(hid), "away_flag": flags.get(aid),
            "score": f"{sh}:{sa}", "is_real": is_real,
        })

    group_tables = {}
    for gid, table in standings.items():
        ranked = sorted(table.items(),
                        key=lambda kv: (kv[1]["pts"], kv[1]["gf"] - kv[1]["ga"],
                                        kv[1]["gf"], elos.get(kv[0], 1500)),
                        reverse=True)
        group_tables[gid] = [
            {"team": names.get(t, t), "flag": flags.get(t), "team_id": t,
             "points": s["pts"], "gd": s["gf"] - s["ga"], "gf": s["gf"]}
            for t, s in ranked
        ]

    qual = rank_and_pair(standings, elos)
    best_thirds = qual["best_thirds"]
    r32_pairs   = qual["r32_pairs"]

    def play_round(pairs, stage_name):
        results, advancing = [], []
        for hid, aid in pairs:
            eh, ea = elos.get(hid, 1500), elos.get(aid, 1500)
            sh, sa = _projected_score(eh, ea)
            w = _winner(eh, ea, hid, aid, sh, sa)
            score_str = f"{sh}:{sa}" + (" (n.E.)" if sh == sa else "")
            results.append({
                "stage": stage_name,
                "home": names.get(hid, hid), "away": names.get(aid, aid),
                "home_flag": flags.get(hid), "away_flag": flags.get(aid),
                "score": score_str, "winner": names.get(w, w), "winner_id": w,
            })
            advancing.append(w)
        return results, advancing

    bracket = {}
    r32_res, r16_teams = play_round(r32_pairs, "ROUND_OF_32")
    bracket["round_of_32"] = r32_res
    r16_pairs = [(r16_teams[i], r16_teams[i + 1]) for i in range(0, len(r16_teams) - 1, 2)]
    r16_res, qf_teams = play_round(r16_pairs, "ROUND_OF_16")
    bracket["round_of_16"] = r16_res
    qf_pairs = [(qf_teams[i], qf_teams[i + 1]) for i in range(0, len(qf_teams) - 1, 2)]
    qf_res, sf_teams = play_round(qf_pairs, "QUARTERFINAL")
    bracket["quarterfinal"] = qf_res
    sf_pairs = [(sf_teams[i], sf_teams[i + 1]) for i in range(0, len(sf_teams) - 1, 2)]
    sf_res, final_teams = play_round(sf_pairs, "SEMIFINAL")
    bracket["semifinal"] = sf_res

    champion = None
    champion_id = None
    if len(final_teams) >= 2:
        final_res, _ = play_round([(final_teams[0], final_teams[1])], "FINAL")
        bracket["final"] = final_res
        champion = final_res[0]["winner"]
        champion_id = final_res[0]["winner_id"]

    return {
        "projected_champion":    champion,
        "projected_champion_id": champion_id,
        "group_stage": {
            "matches": projected_matches, "tables": group_tables,
            "best_thirds": [names.get(t, t) for t in best_thirds],
        },
        "knockout_bracket": bracket,
        "deterministic": True,
        "note": "Einzelprojektion (plausibelster Verlauf). Reale Ergebnisse überschreiben Projektion.",
    }
