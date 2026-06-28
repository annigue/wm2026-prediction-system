"""Ergebnis-Sync aus API-Football (api-sports.io) — zuverlässige Quelle für WM-2026-Ergebnisse.

Hintergrund: Die bisherige world-cup-2026-live-api liefert über /wc/draw keine aktualisierten
Ergebnisse. API-Football (League 1, Season 2026) hat die echten Endstände. Diese Funktion
trägt sie in match_results ein und setzt status=FINISHED — danach greift die bestehende
Recompute-Kette (Elo → Form → Bracket → Prognosen → Simulation).
"""
import unicodedata
from datetime import datetime, timezone

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
    "czechia": "czech republic", "cape verde": "cabo verde", "turkiye": "turkey",
    "congo dr": "dr congo",
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


def _stage_for_round(rnd: str) -> str | None:
    """API-Football-Rundenname -> unsere Stage. None = Gruppenphase/unbekannt.
    Reihenfolge wichtig: 'Quarter-finals'/'3rd Place Final' enthalten 'final'."""
    r = (rnd or "").lower()
    if "round of 32" in r:               return "ROUND_OF_32"
    if "round of 16" in r:               return "ROUND_OF_16"
    if "quarter" in r:                   return "QUARTERFINAL"
    if "semi" in r:                      return "SEMIFINAL"
    if "3rd" in r or "third" in r:       return "THIRD_PLACE"
    if "final" in r:                     return "FINAL"
    return None


def _api_id_to_team(session: Session, fixtures: list) -> dict:
    """API-Team-ID -> unser team_id. Aufgebaut aus ALLEN Fixtures (inkl. Gruppenspiele,
    deren Namen sicher mappen) → KO-Teams werden über die STABILE ID erkannt, unabhängig
    von Schreibvarianten wie 'Cape Verde Islands'."""
    name_map = _name_to_team_id(session)

    def by_name(name):
        n = _norm(name)
        return name_map.get(n) or name_map.get(_ALIAS.get(n, "")) \
            or next((v for k, v in name_map.items() if n and (n in k or k in n)), None)

    out: dict = {}
    for f in fixtures:
        for side in ("home", "away"):
            t = f["teams"][side]
            tid = t.get("id")
            if tid is not None and tid not in out:
                our = by_name(t.get("name") or "")
                if our:
                    out[tid] = our
    return out


def _to_utc_naive(iso: str) -> datetime:
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


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

        # unser Spiel über (Stage aus Runde) + ungeordnete Team-Paarung finden. Die Stage
        # disambiguiert, falls zwei Teams in Gruppe UND KO aufeinandertreffen.
        fstage = _stage_for_round(f["league"].get("round", "")) or "GROUP_STAGE"
        row = session.execute(text("""
            SELECT id, home_team_id, away_team_id FROM matches
            WHERE stage=:st
              AND ((home_team_id=:h AND away_team_id=:a) OR (home_team_id=:a AND away_team_id=:h))
            LIMIT 1"""), {"st": fstage, "h": h_id, "a": a_id}).first()
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

    # Sicherheitsnetz: nicht zuordenbare BEENDETE Spiele sichtbar machen (sonst still übersprungen).
    # Wird in app_state persistiert und in /admin/status + Admin-UI als Warnung angezeigt.
    from app.models.appstate import AppState
    val = "; ".join(summary["unmapped"])
    row = session.get(AppState, "last_unmapped")
    if row:
        row.value = val
    else:
        session.add(AppState(key="last_unmapped", value=val))

    return summary


def _fetch_fixtures() -> list:
    if not settings.football_api_key:
        raise RuntimeError("FOOTBALL_API_KEY fehlt")
    r = httpx.get(f"{settings.football_api_base}/fixtures",
                  headers={"x-apisports-key": settings.football_api_key},
                  params={"league": WC_LEAGUE, "season": WC_SEASON}, timeout=30)
    return r.json().get("response", [])


def sync_ko_fixtures(session: Session, fixtures: list | None = None) -> dict:
    """K.-o.-Paarungen UND Anstoßzeiten aus der offiziellen API in unsere KO-Slots schreiben —
    statt die Gegner selbst zu ermitteln. Eine Runde wird nur gefüllt, wenn ALLE ihre Paarungen
    feststehen (sonst ist die Zuordnung mehrdeutig). Slot-Zuordnung nach Anstoß (frühestes = _01).
    Idempotent; ändert nur matches.home/away_team_id + kickoff_utc. Keine Selbst-Berechnung."""
    summary = {"ko_updated": 0, "rounds_filled": [], "pending": [], "errors": []}
    if fixtures is None:
        try:
            fixtures = _fetch_fixtures()
        except Exception as e:
            summary["errors"].append(str(e))
            return summary

    api_team = _api_id_to_team(session, fixtures)

    by_stage: dict[str, list] = {}
    for f in fixtures:
        st = _stage_for_round(f["league"].get("round", ""))
        if st:
            by_stage.setdefault(st, []).append(f)

    for stage, fxs in by_stage.items():
        slots = [r[0] for r in session.execute(text(
            "SELECT id FROM matches WHERE stage=:s ORDER BY id"), {"s": stage})]
        if not slots:
            continue
        ready = []
        for f in fxs:
            h = api_team.get(f["teams"]["home"].get("id"))
            a = api_team.get(f["teams"]["away"].get("id"))
            if h and a:
                ready.append((f["fixture"]["date"], h, a))
        if not ready:
            continue
        if len(ready) != len(slots):
            summary["pending"].append(f"{stage}: {len(ready)}/{len(slots)} Paarungen bekannt")
            continue
        ready.sort(key=lambda x: x[0])  # frühestes Spiel zuerst → Slot _01
        for slot_id, (date_iso, h, a) in zip(slots, ready):
            ko = _to_utc_naive(date_iso)
            cur = session.execute(text(
                "SELECT home_team_id, away_team_id, kickoff_utc FROM matches WHERE id=:id"),
                {"id": slot_id}).first()
            if cur and (cur[0] != h or cur[1] != a or cur[2] != ko):
                session.execute(text(
                    "UPDATE matches SET home_team_id=:h, away_team_id=:a, kickoff_utc=:k WHERE id=:id"),
                    {"h": h, "a": a, "k": ko, "id": slot_id})
                summary["ko_updated"] += 1
        summary["rounds_filled"].append(stage)

    return summary
