"""V2 — Optimale Startelf + Stärke aus einem Kader.

Hinweis zur Methode: Mit den groben Positionsgruppen (GK/DEF/MID/FWD) entartet das
lineare Zuordnungsproblem zu „beste k Spieler je Gruppe pro Formation". Die Hungarian-
Maschinerie (scipy) wird erst nötig, wenn feinere Positionen vorliegen (z. B. später via
Transfermarkt `sub_position`). Bis dahin ist Top-k-je-Gruppe optimal und genügt.

Eine Formation = Anzahl pro Gruppe. Gewählt wird die Formation mit maximaler XI-Stärke
(= datengetriebene „beste Aufstellung" für den jeweiligen Kader).
"""
from app.services.squad_strength import (
    player_strength, POSITION_WEIGHT, BENCH_BETA, BENCH_TOP,
)

GROUPS = ["Goalkeeper", "Defender", "Midfielder", "Attacker"]

# Formationen als Gruppen-Counts (Torwart immer 1; Σ Feldspieler = 10).
FORMATIONS = {
    "4-3-3":   {"Goalkeeper": 1, "Defender": 4, "Midfielder": 3, "Attacker": 3},
    "4-4-2":   {"Goalkeeper": 1, "Defender": 4, "Midfielder": 4, "Attacker": 2},
    "4-2-3-1": {"Goalkeeper": 1, "Defender": 4, "Midfielder": 5, "Attacker": 1},
    "3-5-2":   {"Goalkeeper": 1, "Defender": 3, "Midfielder": 5, "Attacker": 2},
    "5-3-2":   {"Goalkeeper": 1, "Defender": 5, "Midfielder": 3, "Attacker": 2},
    "3-4-3":   {"Goalkeeper": 1, "Defender": 3, "Midfielder": 4, "Attacker": 3},
}


def optimal_lineup(players: list[dict]) -> dict | None:
    """players: [{name, position, market_value_eur}, …].
    Nutzt nur Spieler MIT Marktwert. Gibt die beste Formation oder None (zu wenig Daten)."""
    by_group: dict[str, list] = {g: [] for g in GROUPS}
    for p in players:
        s = player_strength(p.get("market_value_eur"))
        if s is None:
            continue
        g = p.get("position")
        if g in by_group:
            by_group[g].append((s, p))
    for g in by_group:
        by_group[g].sort(key=lambda x: -x[0])

    best = None
    for fname, counts in FORMATIONS.items():
        if any(len(by_group[g]) < k for g, k in counts.items()):
            continue  # nicht genug bewertete Spieler für diese Formation
        xi, strength = [], 0.0
        for g, k in counts.items():
            for s, p in by_group[g][:k]:
                strength += POSITION_WEIGHT.get(g, 1.0) * s
                xi.append({"name": p.get("name"), "position": g,
                           "market_value_eur": p.get("market_value_eur"), "strength": round(s, 3)})
        if best is None or strength > best["xi_strength"]:
            best = {"formation": fname, "xi": xi, "xi_strength": round(strength, 3)}

    if best is None:
        return None

    used = {x["name"] for x in best["xi"]}
    bench = sorted(
        (s for p in players if p.get("name") not in used
         and (s := player_strength(p.get("market_value_eur"))) is not None),
        reverse=True,
    )[:BENCH_TOP]
    best["team_strength"] = round(best["xi_strength"] + BENCH_BETA * sum(bench), 3)
    best["valued_players"] = sum(len(v) for v in by_group.values())
    return best
