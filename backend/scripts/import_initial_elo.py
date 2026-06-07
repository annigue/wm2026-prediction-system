#!/usr/bin/env python3
"""
Initial-Elo-Import — ersetzt manuelle Seed-Elos durch eine reproduzierbare externe
Standardquelle: World Football Elo Ratings (eloratings.net).

  A) Datei:  python scripts/import_initial_elo.py --file data/eloratings_2026-06-06.txt --eloratings
  B) URL:    python scripts/import_initial_elo.py --url <download-link>
  +--write-db: team_features.elo_rating + elo_ratings-Audit (reason=eloratings_init) schreiben.

KEINE Fantasiewerte: ohne gültigen Input bricht das Skript ab.
"""

from __future__ import annotations
import argparse
import csv
import io
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
OUT_JSON = os.path.join(DATA_DIR, "initial_elo.json")

ELO_NAME_OVERRIDES = {
    "United States": "usa", "USA": "usa",
    "South Korea": "south_korea", "Korea Republic": "south_korea",
    "Ivory Coast": "ivory_coast", "Cote d'Ivoire": "ivory_coast",
    "DR Congo": "dr_congo", "Congo DR": "dr_congo",
    "Cape Verde": "cape_verde", "Czechia": "czech_republic", "Czech Republic": "czech_republic",
    "Bosnia": "bosnia", "Bosnia and Herzegovina": "bosnia",
    "New Zealand": "new_zealand", "Saudi Arabia": "saudi_arabia", "South Africa": "south_africa",
}


def _build_country_to_id() -> dict[str, str]:
    mapping: dict[str, str] = {}

    def _ingest(teams):
        for t in teams:
            mapping[t["country"].lower()] = t["id"]
            mapping[t["name"].lower()] = t["id"]

    from scripts.seed_data import TEAMS as SEED_TEAMS
    _ingest(SEED_TEAMS)
    try:
        from scripts.import_wc2026 import TEAMS as WC_TEAMS
        _ingest(WC_TEAMS)
    except Exception:
        pass
    for name, tid in ELO_NAME_OVERRIDES.items():
        mapping[name.lower()] = tid
    return mapping


def _resolve(name: str, name_to_id: dict[str, str]) -> str | None:
    return name_to_id.get(name.strip().lower())


def _parse_rows(text: str) -> list[tuple[str, float]]:
    delim = "\t" if text.count("\t") >= text.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    rows = [r for r in reader if r and any(c.strip() for c in r)]
    if not rows:
        return []
    header = [c.strip().lower() for c in rows[0]]
    name_col = next((i for i, c in enumerate(header) if c in ("team", "country", "nation", "name")), None)
    rating_col = next((i for i, c in enumerate(header) if c in ("rating", "elo", "points", "elo rating")), None)
    data_rows = rows[1:] if name_col is not None else rows
    out: list[tuple[str, float]] = []
    for r in data_rows:
        try:
            if name_col is not None and rating_col is not None:
                out.append((r[name_col].strip(), float(r[rating_col])))
            else:
                name = next(c for c in r if not c.strip().replace(".", "").isdigit())
                rating = next(float(c) for c in r
                              if c.strip().replace(".", "").isdigit() and 1000 <= float(c) <= 2500)
                out.append((name.strip(), rating))
        except (ValueError, StopIteration, IndexError):
            continue
    return out


def parse_eloratings_blob(text: str, name_to_id: dict[str, str]) -> tuple[dict[str, float], list[str]]:
    """Name-verankerte Extraktion für den eloratings.net-Export (verkettete Spalten)."""
    resolved: dict[str, float] = {}
    matched: list[str] = []
    for name_key in sorted(name_to_id, key=len, reverse=True):
        if len(name_key) < 4:
            continue
        tid = name_to_id[name_key]
        if tid in resolved:
            continue
        m = re.search(r"(?<=\d)" + re.escape(name_key) + r"(\d{4})", text, re.IGNORECASE)
        if m:
            resolved[tid] = float(m.group(1))
            matched.append(name_key)
    return resolved, matched


def load_source(args) -> str:
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            return f.read()
    if args.url:
        import urllib.request
        with urllib.request.urlopen(args.url, timeout=30) as resp:  # noqa: S310
            return resp.read().decode("utf-8", errors="replace")
    raise SystemExit("FEHLER: --file oder --url nötig. Es werden KEINE Werte erfunden.")


def main():
    ap = argparse.ArgumentParser(description="Initial-Elo aus eloratings.net importieren")
    ap.add_argument("--file")
    ap.add_argument("--url")
    ap.add_argument("--eloratings", action="store_true", help="eloratings.net-Blob-Format erzwingen")
    ap.add_argument("--write-db", action="store_true")
    args = ap.parse_args()

    raw = load_source(args)
    name_to_id = _build_country_to_id()

    resolved: dict[str, float] = {}
    for name, rating in _parse_rows(raw):
        tid = _resolve(name, name_to_id)
        if tid:
            resolved[tid] = round(rating, 1)

    if args.eloratings or len(resolved) < 20:
        blob_resolved, _ = parse_eloratings_blob(raw, name_to_id)
        if len(blob_resolved) > len(resolved):
            print(f"  eloratings-Blob-Parser: {len(blob_resolved)} Teams erkannt")
            resolved = blob_resolved

    if not resolved:
        raise SystemExit("FEHLER: Keine (Name, Rating) erkannt. Format prüfen.")

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(resolved, f, indent=2, ensure_ascii=False, sort_keys=True)
    print(f"✓ {len(resolved)} Teams zugeordnet → {OUT_JSON}")

    from scripts.seed_data import TEAMS as SEED_TEAMS
    missing = [t["id"] for t in SEED_TEAMS if t["id"] not in resolved]
    if missing:
        print(f"⚠ {len(missing)} WM-Teams ohne externen Elo (behalten Seed-Wert): {missing}")

    if args.write_db:
        _write_db(resolved)


def _write_db(resolved: dict[str, float]):
    from dotenv import load_dotenv
    load_dotenv()
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from app.models.team import TeamFeature, EloRating

    url = os.getenv("DATABASE_URL_SYNC", "postgresql+psycopg2://wm2026:wm2026@localhost:5432/wm2026")
    engine = create_engine(url)
    Session = sessionmaker(bind=engine)
    written = 0
    with Session() as s:
        for tid, rating in resolved.items():
            feat = s.execute(
                select(TeamFeature).where(TeamFeature.team_id == tid)
                .order_by(TeamFeature.snapshot_date.desc()).limit(1)
            ).scalar_one_or_none()
            if not feat:
                continue
            feat.elo_rating = rating
            feat.data_source = "eloratings_init"
            s.add(EloRating(team_id=tid, rating=rating, reason="eloratings_init"))
            written += 1
        s.commit()
    engine.dispose()
    print(f"✓ DB aktualisiert: {written} Teams (data_source=eloratings_init, snapshot {date.today()})")


if __name__ == "__main__":
    main()
