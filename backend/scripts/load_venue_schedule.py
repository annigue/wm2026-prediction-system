"""Einmaliger Loader: verknüpft die 72 Gruppenspiele mit ihren Stadien (venue_id).

Quelle: offizieller FIFA-Spielplan WM 2026 (Spiel → Stadion). Die world-cup-2026-live-api
liefert KEINE Venue-Daten → diese Zuordnung kommt aus der offiziellen, öffentlichen Quelle.
Match-Schlüssel ist die (ungeordnete) Team-Paarung (match_number ≠ FIFA-Spielnummer).

Ergänzt außerdem die zwei fehlenden echten WM-Spielorte (Atlanta, Seattle); die im Seed
enthaltenen Nicht-Spielorte Denver/Las Vegas bleiben unberührt (ungenutzt).

Aufruf:  python scripts/load_venue_schedule.py
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Fehlende echte Spielorte (id, name, city, country, altitude_m, lat, lon, timezone)
MISSING_VENUES = [
    ("mercedes_benz", "Mercedes-Benz Stadium", "Atlanta, GA", "USA", 320, 33.7553, -84.4006, "America/New_York"),
    ("lumen_field",   "Lumen Field",           "Seattle, WA", "USA",   5, 47.5952, -122.3316, "America/Los_Angeles"),
]

# Stadion-Key → Stadt-Token (zur Auflösung der venue_id über venues.city)
STADIUM_CITY = {
    "azteca": "Mexico City", "akron": "Guadalajara", "bbva": "Monterrey",
    "bmo": "Toronto", "bc_place": "Vancouver", "sofi": "Inglewood",
    "gillette": "Foxborough", "metlife": "East Rutherford", "levis": "Santa Clara",
    "lincoln": "Philadelphia", "nrg": "Houston", "att": "Arlington",
    "hard_rock": "Miami Gardens", "atlanta": "Atlanta", "seattle": "Seattle",
    "arrowhead": "Kansas City",
}

# Offizieller Spielplan: (home_id, away_id, stadion_key) — Reihenfolge egal (Paarung).
SCHEDULE = [
    ("mexico","south_africa","azteca"),("south_korea","czech_republic","akron"),
    ("canada","bosnia","bmo"),("usa","paraguay","sofi"),("haiti","scotland","gillette"),
    ("australia","turkey","bc_place"),("brazil","morocco","metlife"),("qatar","switzerland","levis"),
    ("ivory_coast","ecuador","lincoln"),("germany","curacao","nrg"),("netherlands","japan","att"),
    ("sweden","tunisia","bbva"),("saudi_arabia","uruguay","hard_rock"),("spain","cape_verde","atlanta"),
    ("iran","new_zealand","sofi"),("belgium","egypt","seattle"),("france","senegal","metlife"),
    ("iraq","norway","gillette"),("argentina","algeria","arrowhead"),("austria","jordan","levis"),
    ("ghana","panama","bmo"),("england","croatia","att"),("portugal","dr_congo","nrg"),
    ("uzbekistan","colombia","azteca"),("czech_republic","south_africa","atlanta"),("switzerland","bosnia","sofi"),
    ("canada","qatar","bc_place"),("mexico","south_korea","akron"),("brazil","haiti","lincoln"),
    ("scotland","morocco","gillette"),("turkey","paraguay","levis"),("usa","australia","seattle"),
    ("germany","ivory_coast","bmo"),("ecuador","curacao","arrowhead"),("netherlands","sweden","nrg"),
    ("tunisia","japan","bbva"),("uruguay","cape_verde","hard_rock"),("spain","saudi_arabia","atlanta"),
    ("belgium","iran","sofi"),("new_zealand","egypt","bc_place"),("norway","senegal","metlife"),
    ("france","iraq","lincoln"),("argentina","austria","att"),("jordan","algeria","levis"),
    ("england","ghana","gillette"),("panama","croatia","bmo"),("portugal","uzbekistan","nrg"),
    ("colombia","dr_congo","akron"),("scotland","brazil","hard_rock"),("morocco","haiti","atlanta"),
    ("switzerland","canada","bc_place"),("bosnia","qatar","seattle"),("czech_republic","mexico","azteca"),
    ("south_africa","south_korea","bbva"),("curacao","ivory_coast","lincoln"),("ecuador","germany","metlife"),
    ("japan","sweden","att"),("tunisia","netherlands","arrowhead"),("turkey","usa","sofi"),
    ("paraguay","australia","levis"),("norway","france","gillette"),("senegal","iraq","bmo"),
    ("egypt","iran","seattle"),("new_zealand","belgium","bc_place"),("cape_verde","saudi_arabia","nrg"),
    ("uruguay","spain","akron"),("panama","england","metlife"),("croatia","ghana","lincoln"),
    ("algeria","austria","arrowhead"),("jordan","argentina","att"),("colombia","portugal","hard_rock"),
    ("dr_congo","uzbekistan","atlanta"),
]


def main():
    assert len(SCHEDULE) == 72, f"Erwartet 72 Spiele, habe {len(SCHEDULE)}"
    engine = create_engine(settings.database_url_sync)
    Session = sessionmaker(bind=engine)
    with Session() as s:
        # 1) Fehlende Spielorte ergänzen (idempotent)
        for vid, name, city, country, alt, lat, lon, tz in MISSING_VENUES:
            exists = s.execute(text("SELECT 1 FROM venues WHERE id=:id"), {"id": vid}).scalar()
            if not exists:
                s.execute(text("""INSERT INTO venues (id,name,city,country,altitude_m,lat,lon,timezone)
                    VALUES (:id,:name,:city,:country,:alt,:lat,:lon,:tz)"""),
                    {"id": vid, "name": name, "city": city, "country": country,
                     "alt": alt, "lat": lat, "lon": lon, "tz": tz})
                print(f"  + Venue ergänzt: {name} ({city})")
        s.commit()

        # 2) Stadion-Key → venue_id auflösen (über Stadt)
        key_to_vid = {}
        for key, city in STADIUM_CITY.items():
            vid = s.execute(text("SELECT id FROM venues WHERE city ILIKE :c ORDER BY id LIMIT 1"),
                            {"c": f"%{city}%"}).scalar()
            assert vid, f"Kein Venue für Stadt '{city}' (Key {key})"
            key_to_vid[key] = vid

        # 3) Team-Paarung → venue_id
        pair_to_vid = {frozenset((h, a)): key_to_vid[k] for h, a, k in SCHEDULE}

        # 4) Gruppenspiele aktualisieren
        rows = s.execute(text(
            "SELECT id, home_team_id, away_team_id FROM matches WHERE stage='GROUP_STAGE'")).all()
        matched, unmatched = 0, []
        for mid, h, a in rows:
            vid = pair_to_vid.get(frozenset((h, a)))
            if vid:
                s.execute(text("UPDATE matches SET venue_id=:v WHERE id=:m"), {"v": vid, "m": mid})
                matched += 1
            else:
                unmatched.append((mid, h, a))
        s.commit()
        print(f"\n  Gruppenspiele verknüpft: {matched}/72")
        if unmatched:
            print("  NICHT zugeordnet:")
            for u in unmatched:
                print("   ", u)
    engine.dispose()


if __name__ == "__main__":
    main()
