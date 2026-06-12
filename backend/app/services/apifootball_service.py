"""Ergebnis-Sync aus API-Football (api-sports.io) — zuverlässige Quelle für WM-2026-Ergebnisse.

Hintergrund: Die bisherige world-cup-2026-live-api liefert über /wc/draw keine aktualisierten
Ergebnisse. API-Football (League 1, Season 2026) hat die echten Endstände. Diese Funktion
trägt sie in match_results ein und setzt status=FINISHED — danach greift die bestehende
Recompute-Kette (Elo → Form → Bracket → Prognosen → Simulation).
"""
import unicodedata

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.models.match import MatchResult

WC_LEAGUE, WC_SEASON = 1, 2026
FINISHED = {"FT", "AET", "PEN"}

# unser home_country (norm) -> API-Football-Teamname (norm), für Abweichungen
_ALIAS = {
    "united states": "usa", "south korea": "korea republic", "ivory coast": "cote divoire",
    "czechia": "czech republic", "cape verde": "cabo verde",
}


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return " ".join("".join(c for c in s if c.isalnum() or c == " ").split())


def _name_to_team_id(session: Session) -> dict:
    """norm(home_country) und norm(name) -> team_id (für robustes Mapping)."""
    m = {}
    for tid, name, country in session.execute(text("SELECT id, name, home_country FROM teams")).all():
        for v in (country, name):
            if v:
                m[_norm(v)] = tid
    return m


def sync_results(session: Session) -> dict:
    """Holt beendete WM-Spiele aus API-Football und trägt Ergebnisse ein. Idempotent."""
    summary = {"results_added": 0, "results_updated": 0, "unmapped": [], "errors": []}
    if not settings.football_api_key:
        summary["errors"].append("FOOTBALL_API_KEY fehlt")
        return summary
    try:
        r = httpx.get(f"{settings.football_api_base}/fixtures",
                      headers={"x-apisports-key": settings.football_api_key},
                      params={"league": WC_LEAGUE, "season": WC_SEASON}, timeout=30)
        fixtures = r.json().get("response", [])
    except Exception as e:
        summary["errors"].append(f"fixtures: {e}")
        return summary

    name_map = _name_to_team_id(session)

    def tid(name):
        n = _norm(name)
        return name_map.get(n) or name_map.get(_ALIAS.get(n, "")) \
            or next((v for k, v in name_map.items() if n and (n in k or k in n)), None)

    for f in fixtures:
        if f["fixture"]["status"]["short"] not in FINISHED:
            continue
        h_id, a_id = tid(f["teams"]["home"]["name"]), tid(f["teams"]["away"]["name"])
        gh, ga = f["goals"]["home"], f["goals"]["away"]
        if not h_id or not a_id or gh is None or ga is None:
            summary["unmapped"].append(f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}")
            continue

        # unser Spiel über ungeordnete Team-Paarung finden
        row = session.execute(text("""
            SELECT id, home_team_id, away_team_id FROM matches
            WHERE stage='GROUP_STAGE'
              AND ((home_team_id=:h AND away_team_id=:a) OR (home_team_id=:a AND away_team_id=:h))
            LIMIT 1"""), {"h": h_id, "a": a_id}).first()
        if not row:
            summary["unmapped"].append(f"{h_id} vs {a_id} (kein DB-Spiel)")
            continue
        mid, db_home, _ = row
        # Tore auf unsere Heim/Auswärts-Zuordnung mappen
        home_goals, away_goals = (gh, ga) if db_home == h_id else (ga, gh)

        st = f["fixture"]["status"]["short"]
        existing = session.get(MatchResult, mid)
        if existing:
            existing.home_goals, existing.away_goals = home_goals, away_goals
            existing.source = "apifootball"
            summary["results_updated"] += 1
        else:
            session.add(MatchResult(  # ORM → setzt alle NOT-NULL-Defaults (recorded_at etc.)
                match_id=mid, home_goals=home_goals, away_goals=away_goals,
                went_to_extra_time=st in ("AET", "PEN"), went_to_penalties=st == "PEN",
                source="apifootball"))
            summary["results_added"] += 1
        session.execute(text("UPDATE matches SET status='FINISHED' WHERE id=:id"), {"id": mid})

    return summary
