#!/usr/bin/env python3
"""
Form-DB-Refresh — setzt form_score ALLER Teams auf den datengetriebenen Wert.

Deckt (anders als form_engine.update_all_forms) ALLE Teams ab — kein Seed-/Legacy-Wert
verbleibt. Teams ohne reale Ergebnisse → form_score = 0.0. Protokolliert jeden Overwrite.

Aufruf:  cd backend && venv/bin/python scripts/refresh_form.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services.form_engine import compute_form


def main():
    url = os.getenv("DATABASE_URL_SYNC",
                    "postgresql+psycopg2://wm2026:wm2026@localhost:5432/wm2026")
    engine = create_engine(url)
    Session = sessionmaker(bind=engine)

    overwritten = []
    unchanged = 0
    with Session() as s:
        rows = s.execute(text("""
            SELECT DISTINCT ON (team_id) team_id, form_score, data_source, snapshot_date
            FROM   team_features
            ORDER  BY team_id, snapshot_date DESC
        """)).fetchall()

        for team_id, old_form, old_source, _ in rows:
            result = compute_form(team_id, s)
            new_form = result.form_score
            s.execute(text("""
                UPDATE team_features
                SET    form_score = :fs, data_source = 'form_engine_v2'
                WHERE  team_id = :tid
                  AND  snapshot_date = (
                          SELECT MAX(snapshot_date) FROM team_features WHERE team_id = :tid
                       )
            """), {"fs": new_form, "tid": team_id})

            old_val = float(old_form) if old_form is not None else 0.0
            if abs(old_val - new_form) > 1e-9 or (old_source or "").startswith("seed"):
                overwritten.append((team_id, old_val, new_form, old_source, result.n_matches))
            else:
                unchanged += 1
        s.commit()
    engine.dispose()

    print(f"\n{'='*70}\nFORM-REFRESH  ({len(rows)} Teams)\n{'='*70}")
    print(f"  Überschrieben: {len(overwritten)}   Unverändert: {unchanged}\n")
    if overwritten:
        print(f"  {'team_id':18}{'alt':>8}{'neu':>8}{'n':>4}  alte Quelle")
        for tid, old, new, src, n in sorted(overwritten, key=lambda x: x[1], reverse=True):
            print(f"  {tid:18}{old:>8.3f}{new:>8.3f}{n:>4}  {src}")
    leak = sum(1 for _, _, new, _, n in overwritten if n == 0 and abs(new) > 1e-9)
    print(f"\n  ✓ Seed-Leakage nach Refresh: {leak} (erwartet 0)")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
