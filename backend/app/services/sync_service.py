"""
Synchronisiert WM-Daten von world-cup-2026-live-api (RapidAPI).

Idempotenter Sync: aktualisiert Match-Status/Kickoff und trägt Ergebnisse nach.
Gruppen/Spielplan bleiben sonst erhalten (kein doppeltes Anlegen). Status-Abfrage
macht KEINEN API-Call (gibt nur den letzten bekannten Stand zurück).

Rebuild-Hinweis (Recovery 2026-06-07): defensiv rekonstruiert; vor Verlass auf den
Live-Sync gegen die API testen. Das Namens-Mapping wird aus der DB (home_country) gebaut.
"""

from __future__ import annotations
import re
import unicodedata
from datetime import datetime, timezone
import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings

HOST = "world-cup-2026-live-api.p.rapidapi.com"
BASE = f"https://{HOST}"

STATUS_MAP = {1: "SCHEDULED", 2: "LIVE", 3: "FINISHED", 0: "POSTPONED"}

_last_status: dict = {
    "requests_remaining": None,
    "requests_limit": None,
    "last_sync": None,
    "last_check": None,
}

# Namens-Abweichungen API → kanonische Normalform (Rest kommt aus der DB home_country)
_ALIASES = {
    "d r congo": "dr congo", "dr congo": "dr congo",
    "united states": "usa", "usa": "usa",
    "korea republic": "south korea", "south korea": "south korea",
    "ir iran": "iran",
}


def _headers() -> dict:
    return {"X-RapidAPI-Key": settings.rapidapi_key, "X-RapidAPI-Host": HOST}


def _parse_rate_limits(response) -> None:
    rem = response.headers.get("X-RateLimit-Requests-Remaining")
    lim = response.headers.get("X-RateLimit-Requests-Limit")
    if rem is not None:
        _last_status["requests_remaining"] = rem
    if lim is not None:
        _last_status["requests_limit"] = lim
    _last_status["last_check"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"


def get_status() -> dict:
    """Letzter bekannter Sync-/Rate-Limit-Status (KEIN API-Call)."""
    return dict(_last_status)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    return _ALIASES.get(s, s)


def _build_name_map(session: Session) -> dict[str, str]:
    """Normalisierter Ländername → team_id (aus DB: home_country, name, short_name)."""
    rows = session.execute(text("SELECT id, name, short_name, home_country FROM teams")).fetchall()
    m: dict[str, str] = {}
    for tid, name, short, country in rows:
        for cand in (country, name, short, tid):
            if cand:
                m.setdefault(_norm(cand), tid)
    return m


def _team_id(name: str, name_map: dict[str, str]) -> str | None:
    key = _norm(name)
    if key in name_map:
        return name_map[key]
    for k, v in name_map.items():  # toleranter Teilstring-Fallback
        if k and (k in key or key in k):
            return v
    return None


def sync_all(session: Session) -> dict:
    """Holt Standings + Draw und aktualisiert idempotent Status/Kickoff/Ergebnisse."""
    summary = {"fixtures_updated": 0, "results_added": 0, "unmapped": [], "errors": []}
    name_map = _build_name_map(session)

    # ── Draw: Fixtures + Ergebnisse ────────────────────────────────────────────
    try:
        r = httpx.get(f"{BASE}/wc/draw", headers=_headers(), timeout=25)
        _parse_rate_limits(r)
        r.raise_for_status()
        fixtures = r.json().get("data", [])
    except Exception as e:
        summary["errors"].append(f"draw: {e}")
        fixtures = []

    for f in fixtures:
        mid = f"WC2026_{f.get('matchId')}"
        status = STATUS_MAP.get(f.get("status", 1), "SCHEDULED")
        home_id = _team_id(f.get("home", ""), name_map) if f.get("home") else None
        away_id = _team_id(f.get("away", ""), name_map) if f.get("away") else None
        if f.get("home") and not home_id:
            summary["unmapped"].append(f.get("home"))
        if f.get("away") and not away_id:
            summary["unmapped"].append(f.get("away"))

        kickoff = None
        if f.get("kickoff"):
            try:
                kickoff = datetime.fromisoformat(
                    f["kickoff"].replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                pass

        exists = session.execute(text("SELECT 1 FROM matches WHERE id = :id"),
                                 {"id": mid}).fetchone()
        if exists:
            session.execute(text("""
                UPDATE matches SET status = :st,
                       kickoff_utc = COALESCE(:k, kickoff_utc),
                       home_team_id = COALESCE(home_team_id, :h),
                       away_team_id = COALESCE(away_team_id, :a)
                WHERE id = :id
            """), {"st": status, "k": kickoff, "h": home_id, "a": away_id, "id": mid})
            summary["fixtures_updated"] += 1

        # Ergebnis nachtragen (idempotent)
        if status == "FINISHED":
            sh, sa = f.get("scoreHome"), f.get("scoreAway")
            if sh is not None and sa is not None and exists:
                has = session.execute(text("SELECT 1 FROM match_results WHERE match_id = :id"),
                                      {"id": mid}).fetchone()
                if not has:
                    session.execute(text("""
                        INSERT INTO match_results (match_id, home_goals, away_goals, source)
                        VALUES (:id, :h, :a, 'world-cup-2026-live-api')
                    """), {"id": mid, "h": int(sh), "a": int(sa)})
                    summary["results_added"] += 1

    _last_status["last_sync"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"
    session.commit()
    summary["unmapped"] = sorted(set(summary["unmapped"]))
    return {**summary, **_last_status}
