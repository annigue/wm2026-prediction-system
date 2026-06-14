"""Lädt historische Länderspiel-Ergebnisse (martj42/international_results) → international_results.

Nur Tore (keine Spieler-/SPI-Daten). Datenbasis für Attack-/Defense-Ratings.
Idempotent: leert die Tabelle und lädt neu. Filtert ab CUTOFF und nur Spiele mit ≥1 WM-Team.

Aufruf:  PYTHONPATH=. python scripts/load_international_results.py
"""
import csv
import io
import unicodedata
from datetime import date, datetime

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base
from app.models.results_history import InternationalResult

CSV_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
LOCAL_FALLBACK = "/tmp/intl_results.csv"
CUTOFF = date(2021, 1, 1)

# dataset-norm -> unser home_country-norm (nur wo abweichend benannt)
ALIAS = {
    "cote divoire": "ivory coast",
    "turkiye": "turkey",
    "czechia": "czech republic",
    "cabo verde": "cape verde",
    "korea republic": "south korea",
    "bosnia and herzegovina": "bosnia",
    "united states virgin islands": "",  # nie WM-Team, explizit ignorieren
}


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return " ".join("".join(c for c in s if c.isalnum() or c == " ").split())


def main() -> None:
    eng = create_engine(settings.database_url_sync)
    Base.metadata.create_all(eng)  # legt international_results an, falls fehlt
    Session = sessionmaker(bind=eng)

    try:
        txt = httpx.get(CSV_URL, timeout=90).text
        src = "github"
    except Exception:
        txt = open(LOCAL_FALLBACK).read()
        src = "local"

    with Session() as s:
        name_to_id: dict[str, str] = {}
        for tid, name, country in s.execute(text("SELECT id, name, home_country FROM teams")):
            for v in (country, name):
                if v:
                    name_to_id[_norm(v)] = tid

        def tid(nm: str):
            n = _norm(nm)
            return name_to_id.get(n) or name_to_id.get(ALIAS.get(n, ""))

        s.execute(text("DELETE FROM international_results"))
        rdr = csv.DictReader(io.StringIO(txt))
        ins = 0
        for row in rdr:
            hs, as_ = row["home_score"], row["away_score"]
            if hs in ("", "NA") or as_ in ("", "NA"):
                continue
            try:
                d = datetime.strptime(row["date"], "%Y-%m-%d").date()
            except ValueError:
                continue
            if d < CUTOFF:
                continue
            h_id, a_id = tid(row["home_team"]), tid(row["away_team"])
            if not h_id and not a_id:
                continue
            s.add(InternationalResult(
                match_date=d, home_name=row["home_team"][:80], away_name=row["away_team"][:80],
                home_team_id=h_id, away_team_id=a_id,
                home_goals=int(hs), away_goals=int(as_),
                tournament=(row.get("tournament") or "")[:80],
                neutral=(row.get("neutral", "").upper() == "TRUE"),
            ))
            ins += 1
        s.commit()

        # Abdeckungs-Report: Spiele pro WM-Team
        rows = s.execute(text("""
            SELECT t.id, count(r.id) AS n
            FROM teams t
            LEFT JOIN international_results r
              ON r.home_team_id = t.id OR r.away_team_id = t.id
            GROUP BY t.id ORDER BY n
        """)).all()
        zero = [r[0] for r in rows if r[1] == 0]
        ns = [r[1] for r in rows]
        print(f"Quelle: {src} · eingefügt: {ins} Spiele (ab {CUTOFF})")
        print(f"Spiele/Team — min {min(ns)} · median {sorted(ns)[len(ns)//2]} · max {max(ns)}")
        print(f"Teams OHNE Spiele ({len(zero)}): {zero}")

    eng.dispose()


if __name__ == "__main__":
    main()
