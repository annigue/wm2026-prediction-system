"""V2 — Import der 48 WM-Kader (API-Football) + Join der Marktwerte (Transfermarkt).

Schritt 1+2 der Aufstellungs-Engine:
  1) 48 WM-2026-Kader aus API-Football laden,
  2) je Spieler den Transfermarkt-Marktwert über robustes Name(+Alter)-Matching joinen,
     Coverage-Report pro Nation, Fallback-Markierung.

Schreibt NUR in die neue Tabelle `players` (additiv; V1 unberührt). Idempotent (Full-Refresh).
Aufruf:  PYTHONPATH=. python scripts/import_v2_squads.py
"""
import os, sys, unicodedata, difflib, datetime
import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import settings
from app.database import Base
from app.models import lineup  # noqa: F401  (registriert Player auf Base.metadata)

API_BASE = "https://v3.football.api-sports.io"
WC_LEAGUE, WC_SEASON = 1, 2026


def norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return " ".join("".join(c for c in s if c.isalnum() or c == " ").split())


# Aliasse: unser home_country -> API-Football-Teamname bzw. TM-Staatsbürgerschaft
ALIAS = {
    "united states": "usa", "south korea": "korea republic", "ivory coast": "cote divoire",
    "czechia": "czech republic", "cape verde": "cabo verde",
}


def api_get(key, ep, **params):
    r = httpx.get(f"{API_BASE}{ep}", headers={"x-apisports-key": key}, params=params, timeout=30)
    return r.json().get("response", [])


def match_player(api_name, api_age, pool):
    """pool: list of dicts {nname, birth_year, mv, name}. Gibt (mv, tm_name) oder (None, None).
    Geburtsjahr dominiert (disambiguiert Namensvetter); Marktwert ist nur milder Tiebreaker."""
    nn = norm(api_name)
    if not nn:
        return None, None
    by = {p["nname"]: p for p in pool}
    names = list(by.keys())
    target_by = (datetime.date.today().year - int(api_age)) if api_age else None

    cands = set(difflib.get_close_matches(nn, names, n=6, cutoff=0.6))
    if nn in by:
        cands.add(nn)
    toks = nn.split()
    last = toks[-1] if toks else nn
    first = toks[0] if toks else nn
    for p in pool:
        ptoks = p["nname"].split()
        if last and last in ptoks:
            cands.add(p["nname"])
        if first and len(first) > 3 and first in ptoks:
            cands.add(p["nname"])
    if not cands:
        return None, None

    def score(c):
        p = by[c]
        s = difflib.SequenceMatcher(None, nn, c).ratio() * 25
        if target_by and p["birth_year"]:
            s += 60 if abs(p["birth_year"] - target_by) <= 1 else -60   # Geburtsjahr dominiert
        if p["mv"] is not None:
            s += 15                                                     # milder Tiebreaker
        return s

    best = max(cands, key=score)
    p = by[best]
    sim = difflib.SequenceMatcher(None, nn, best).ratio()
    by_ok = bool(target_by and p["birth_year"] and abs(p["birth_year"] - target_by) <= 1)
    if sim < 0.6 and not by_ok:        # zu unsicher → kein Match
        return None, None
    return p["mv"], p["name"]


def main():
    key = settings.football_api_key if hasattr(settings, "football_api_key") else os.environ.get("FOOTBALL_API_KEY", "")
    if not key:
        # direkt aus .env lesen (Fallback)
        for line in open(os.path.join(os.path.dirname(__file__), "..", ".env"), encoding="utf-8", errors="ignore"):
            if line.startswith("FOOTBALL_API_KEY"):
                key = line.split("=", 1)[1].strip().strip("'\"")
    assert key, "FOOTBALL_API_KEY fehlt"

    engine = create_engine(settings.database_url_sync)
    Base.metadata.create_all(engine)  # legt NUR fehlende (V2-)Tabellen an, V1 unberührt
    Session = sessionmaker(bind=engine)

    # unsere 48 WM-Teams
    with Session() as s:
        rows = s.execute(text(
            "SELECT t.id, t.name, t.home_country FROM teams t "
            "JOIN group_memberships g ON g.team_id=t.id")).all()
    our = {r[0]: {"name": r[1], "country": r[2]} for r in rows}
    print(f"Unsere WM-Teams: {len(our)}")

    # API-Football WM-Teams
    api_teams = api_get(key, "/teams", league=WC_LEAGUE, season=WC_SEASON)
    api_map = {norm(x["team"]["name"]): x["team"]["id"] for x in api_teams}
    print(f"API-Football WM-Teams: {len(api_map)}")

    # Transfermarkt laden
    print("Lade Transfermarkt-Datensatz …", flush=True)
    import mlcroissant as mlc, pandas as pd
    ds = mlc.Dataset("https://www.kaggle.com/datasets/davidcariboo/player-scores/croissant/download")
    rs = {r.name: r.uuid for r in ds.metadata.record_sets}
    tm = pd.DataFrame(ds.records(record_set=rs["players.csv"]))
    tm.columns = [c.split("/")[-1] for c in tm.columns]
    for c in tm.select_dtypes("object").columns:
        tm[c] = tm[c].astype(str).str.replace(r"^b'|'$", "", regex=True)
    tm["mv"] = pd.to_numeric(tm["market_value_in_eur"], errors="coerce")
    tm["nname"] = tm["name"].map(norm)
    tm["birth_year"] = pd.to_datetime(tm["date_of_birth"], errors="coerce").dt.year
    tm["cit"] = tm["country_of_citizenship"].map(norm)
    print(f"Transfermarkt-Spieler: {len(tm)}")

    def tm_pool(country):
        nc = norm(country)
        sub = tm[tm.cit.str.contains(nc, na=False)]
        if len(sub) < 11:  # Fallback: global (kleine/abweichend gelabelte Nationen)
            sub = tm
        out = []
        for nn, by, mv, nm in zip(sub["nname"], sub["birth_year"], sub["mv"], sub["name"]):
            out.append({"nname": nn,
                        "birth_year": int(by) if pd.notna(by) else None,
                        "mv": float(mv) if pd.notna(mv) else None,
                        "name": nm})
        return out

    # Import
    with Session() as s:
        s.execute(text("DELETE FROM players"))
        report = []
        unmapped = []
        for tid, info in our.items():
            cand = norm(info["country"])
            api_id = api_map.get(cand) or api_map.get(ALIAS.get(cand, "")) \
                or next((v for k, v in api_map.items() if cand in k or k in cand), None)
            if not api_id:
                m = difflib.get_close_matches(cand, list(api_map), n=1, cutoff=0.7)
                api_id = api_map[m[0]] if m else None
            if not api_id:  # Token-Überlappung (z. B. "dr congo" <-> "congo dr")
                cw = set(cand.split())
                best_t, best_ov = None, 0
                for k, v in api_map.items():
                    ov = len(cw & set(k.split()))
                    if ov > best_ov:
                        best_ov, best_t = ov, v
                api_id = best_t if best_ov >= 1 else None
            if not api_id:
                unmapped.append((tid, info["country"])); continue
            squad = api_get(key, "/players/squads", team=api_id)
            players = squad[0].get("players", []) if squad else []
            pool = tm_pool(info["country"])
            matched = valued = 0
            for p in players:
                mv, tmname = match_player(p.get("name"), p.get("age"), pool)
                if tmname:
                    matched += 1
                if mv is not None:
                    valued += 1
                s.add(lineup.Player(
                    id=f"af{p['id']}", api_football_id=p["id"], name=p.get("name") or "?",
                    nation_team_id=tid, position=p.get("position"), shirt_number=p.get("number"),
                    age=p.get("age"), club=None, market_value_eur=mv,
                    transfermarkt_name=tmname, value_matched=mv is not None,
                ))
            cov = round(100 * valued / max(len(players), 1))
            report.append((tid, len(players), matched, valued, cov))
        s.commit()

    report.sort(key=lambda r: r[4])
    print("\n=== Coverage-Report (Marktwert je Kader) ===")
    print(f"{'Team':16s} Kader matched valued  %    Fallback?")
    fb = []
    for tid, n, m, v, cov in report:
        flag = "  ⚠ FALLBACK V1" if cov < 60 else ""
        if cov < 60:
            fb.append(tid)
        print(f"{tid:16s} {n:4d} {m:6d} {v:6d}  {cov:3d}%{flag}")
    print(f"\nNicht gemappte Teams: {unmapped or 'keine'}")
    print(f"Nationen mit V1-Fallback (<60% Wert-Coverage): {len(fb)} → {fb}")
    total_players = sum(r[1] for r in report)
    total_valued = sum(r[3] for r in report)
    print(f"\nGesamt: {len(report)} Teams · {total_players} Spieler · {total_valued} mit Marktwert "
          f"({round(100*total_valued/max(total_players,1))}%)")
    engine.dispose()


if __name__ == "__main__":
    main()
