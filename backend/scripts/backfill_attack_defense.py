"""Backfill: Attack-/Defense-Ratings in den neuesten team_features-Snapshot schreiben.

Additive ALTER TABLE (rückwärtskompatibel) + compute_ratings. Idempotent.
Aufruf:  PYTHONPATH=. python scripts/backfill_attack_defense.py
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.services.attack_defense_service import compute_ratings, global_mean_goals


def main() -> None:
    eng = create_engine(settings.database_url_sync)
    Session = sessionmaker(bind=eng)
    with Session() as s:
        s.execute(text("ALTER TABLE team_features ADD COLUMN IF NOT EXISTS attack_rating double precision"))
        s.execute(text("ALTER TABLE team_features ADD COLUMN IF NOT EXISTS defense_rating double precision"))
        s.commit()

        mu = global_mean_goals(s)
        ratings = compute_ratings(s)
        upd = 0
        for tid, r in ratings.items():
            res = s.execute(text("""
                UPDATE team_features SET attack_rating = :a, defense_rating = :d
                WHERE team_id = :t
                  AND snapshot_date = (SELECT max(snapshot_date) FROM team_features WHERE team_id = :t)
            """), {"a": r["attack"], "d": r["defense"], "t": tid})
            upd += res.rowcount
        s.commit()

        print(f"μ (Tore/Team/Spiel) = {mu:.3f} · Ratings für {len(ratings)} Teams · {upd} Snapshots aktualisiert")
        top_atk = sorted(ratings.items(), key=lambda x: -x[1]["attack"])[:5]
        top_def = sorted(ratings.items(), key=lambda x: x[1]["defense"])[:5]
        print("Stärkster Angriff:", [(t, r["attack"]) for t, r in top_atk])
        print("Beste Defense   :", [(t, r["defense"]) for t, r in top_def])
    eng.dispose()


if __name__ == "__main__":
    main()
