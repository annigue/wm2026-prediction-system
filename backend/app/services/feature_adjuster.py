"""Feature Adjustment Layer: 4 kontextuelle Faktoren als Elo-Delta.

Datenqualitäts-Härtung (2026-06-06):
  Reduziert von 7 → 4 Faktoren. Entfernt wurden:
    - Durchschnittsalter (age)  — Seed-Schätzung, Importance ≪ Elo, kein Kalibriergewinn
    - Erfahrung (caps)          — Seed-Schätzung, Importance ≪ Elo, kein Kalibriergewinn
    - FIFA-Ranking              — bereits zuvor entfernt (nur noch Elo-Init-Prior)

Faktoren (alle deterministisch / faktisch / reproduzierbar):
    1. Form       — aus echten Ergebnissen (form_engine, Single Source of Truth)
    2. Marktwert  — statischer PRIOR (Transfermarkt), klar gelabelt, eingefroren
    3. Höhe       — Geodaten (Venue + Heimat), faktisch
    4. Reise      — Geopy great_circle, berechnet
    5. Erholung   — Rest-Days/Fatigue aus dem Spielplan (kickoff_utc), berechnet
                    (Hardening 2026-06-06; reproduzierbar, keine externen Daten)
"""

import math
from dataclasses import dataclass

try:
    from geopy.distance import great_circle as _gc
    def _dist_km(lat1, lon1, lat2, lon2) -> float:
        return _gc((lat1, lon1), (lat2, lon2)).km
except ImportError:
    def _dist_km(lat1, lon1, lat2, lon2) -> float:
        # Haversine-Fallback
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))


@dataclass
class Factor:
    name: str
    description: str
    elo_delta: float    # positiv = Vorteil Heimteam
    weight: float


@dataclass
class AdjustmentResult:
    adjusted_home_elo: float
    adjusted_away_elo: float
    total_delta: float
    factors: list[Factor]
    summary: str


class FeatureAdjuster:
    """Berechnet kontextuelle Elo-Anpassungen. Jeder Faktor trägt einen Elo-Delta bei
    (positiv = Heimteam-Vorteil); der Gesamt-Delta wird hälftig auf beide Teams verteilt."""

    # Max. Beitrag pro Feature in Elo-Punkten
    CAPS = {
        "form":     60,
        "market":   50,
        "altitude": 80,
        "travel":   30,
        "rest":     20,
    }

    # Erholung (Fatigue): sanfte Sättigung statt harter Deckelung.
    #   ΔElo = REST_MAX · tanh(rest_diff / REST_SCALE)
    #   Steigung bei 0 = REST_MAX/REST_SCALE = 8 Elo/Tag, asymptotisch ±REST_MAX.
    REST_MAX   = 20.0
    REST_SCALE = 2.5

    def adjust(self, home_team, away_team, home_feat, away_feat, venue,
               rest_home: float | None = None, rest_away: float | None = None) -> AdjustmentResult:
        home_elo = getattr(home_feat, "elo_rating", 1500.0) or 1500.0
        away_elo = getattr(away_feat, "elo_rating", 1500.0) or 1500.0
        factors: list[Factor] = []

        # ── 1. Form ──────────────────────────────────────────────────────────
        fh = getattr(home_feat, "form_score", 0.0) or 0.0
        fa = getattr(away_feat, "form_score", 0.0) or 0.0
        d  = self._cap((fh - fa) * 50, "form")
        factors.append(Factor(
            name="Aktuelle Form",
            description=f"Heim {fh:+.2f} — Auswärts {fa:+.2f} (Skala −1 bis +1)",
            elo_delta=round(d, 1), weight=0.15,
        ))

        # ── 2. Marktwert ──────────────────────────────────────────────────────
        mvh = getattr(home_feat, "market_value_millions", None) or 200.0
        mva = getattr(away_feat, "market_value_millions", None) or 200.0
        ratio = max(mvh, 1.0) / max(mva, 1.0)
        d = self._cap(math.log10(ratio) * 45, "market")
        factors.append(Factor(
            name="Marktwert",
            description=f"Heim {mvh:.0f}M€ — Auswärts {mva:.0f}M€",
            elo_delta=round(d, 1), weight=0.10,
        ))

        # ── 3. Höhenunterschied ───────────────────────────────────────────────
        if venue:
            va  = getattr(venue,      "altitude_m", 0) or 0
            ha  = getattr(home_team,  "home_altitude_m", 0) or 0
            aa  = getattr(away_team,  "home_altitude_m", 0) or 0
            pen_h = max(0, (va - ha) - 500) / 10_000 * 80
            pen_a = max(0, (va - aa) - 500) / 10_000 * 80
            d = self._cap(-pen_h + pen_a, "altitude")
            if abs(d) > 1:
                factors.append(Factor(
                    name="Höhe Spielort",
                    description=f"Stadion {va}m | Heim Heimat {ha}m | Auswärts Heimat {aa}m",
                    elo_delta=round(d, 1), weight=0.08,
                ))

        # ── 4. Reisedistanz ───────────────────────────────────────────────────
        if venue and getattr(home_team, "home_lat", None) and getattr(venue, "lat", None):
            try:
                dh = _dist_km(home_team.home_lat, home_team.home_lon, venue.lat, venue.lon)
                da = _dist_km(away_team.home_lat, away_team.home_lon, venue.lat, venue.lon) \
                     if getattr(away_team, "home_lat", None) else dh
                pen_h = self._cap(max(0, dh - 3000) / 100_000 * 100, "travel")
                pen_a = self._cap(max(0, da - 3000) / 100_000 * 100, "travel")
                d = pen_a - pen_h
                if abs(d) > 2:
                    factors.append(Factor(
                        name="Reisedistanz",
                        description=f"Heim {dh:.0f}km — Auswärts {da:.0f}km zum Spielort",
                        elo_delta=round(d, 1), weight=0.07,
                    ))
            except Exception:
                pass

        # ── 5. Erholung / Fatigue (Rest Days) ─────────────────────────────────
        # Reproduzierbar aus dem Spielplan (kickoff_utc) — siehe prediction_engine._rest_days.
        # Mehr Erholung = Vorteil. Vor dem 1. gespielten Spiel → None → neutral.
        if rest_home is not None and rest_away is not None:
            rest_diff = rest_home - rest_away          # >0 = Heim besser erholt
            d = self._cap(self.REST_MAX * math.tanh(rest_diff / self.REST_SCALE), "rest")
            if abs(d) > 2:
                factors.append(Factor(
                    name="Erholung (Rest Days)",
                    description=f"Heim {rest_home:.1f}d — Auswärts {rest_away:.1f}d seit letztem gespielten Spiel",
                    elo_delta=round(d, 1), weight=0.06,
                ))

        # ── Entfernte Faktoren (Datenqualitäts-Härtung 2026-06-06) ────────────
        # Durchschnittsalter & Erfahrung (Caps): aus dem Modell entfernt (Seed-Schätzwerte,
        # Importance unter Form). DB-Spalten bleiben für die Anzeige, fließen aber NICHT
        # mehr in Prognosen. FIFA-Ranking: nur noch Elo-Init-Prior.

        # ── Gesamt ────────────────────────────────────────────────────────────
        total = round(max(min(sum(f.elo_delta for f in factors), 150), -150), 1)
        adj_h = round(home_elo + total * 0.5, 1)
        adj_a = round(away_elo - total * 0.5, 1)

        factors_sorted = sorted(factors, key=lambda f: abs(f.elo_delta), reverse=True)
        summary = self._summary(home_elo, away_elo, total, factors_sorted)

        return AdjustmentResult(
            adjusted_home_elo=adj_h,
            adjusted_away_elo=adj_a,
            total_delta=total,
            factors=factors_sorted,
            summary=summary,
        )

    def _cap(self, value: float, key: str) -> float:
        c = self.CAPS.get(key, 50)
        return max(min(value, c), -c)

    @staticmethod
    def _summary(elo_h: float, elo_a: float, delta: float, factors: list[Factor]) -> str:
        base_diff = elo_h - elo_a
        if base_diff > 120:   verdict = "Klarer Favorit: Heimteam (Elo-Basis)."
        elif base_diff > 40:  verdict = "Leichter Favorit: Heimteam (Elo-Basis)."
        elif base_diff < -120:verdict = "Klarer Favorit: Auswärtsteam (Elo-Basis)."
        elif base_diff < -40: verdict = "Leichter Favorit: Auswärtsteam (Elo-Basis)."
        else:                 verdict = "Ausgeglichenes Spiel."

        if factors and abs(factors[0].elo_delta) > 5:
            dom = factors[0]
            who = "Heimteam" if dom.elo_delta > 0 else "Auswärtsteam"
            verdict += f" Stärkster Kontextfaktor: {dom.name} (+{abs(dom.elo_delta):.0f} Elo für {who})."

        return verdict
