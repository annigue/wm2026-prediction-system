"""
Controlled Context Injection Layer für die Turniersimulation.

Architektur-Entscheidung:
  - Elo = globale Teamstärke (stabil, kalibriert, langsam veränderlich)
  - Context = lokale Matchvarianz (stochastisch, matchspezifisch, begrenzt)

Zweistufiges Modell:
  1. Deterministischer Anteil: bekannte Feature-Differenzen (Form)
  2. Stochastischer Anteil: Match-zu-Match-Varianz (Kader-Tiefe, Tagesform, KO-Druck, Umwelt)

Constraints:
  - Gesamteffekt gedeckelt auf ±TOTAL_CAP (konservativ, Simulation stabil)
  - Features ergänzen Elo — sie ersetzen es nicht
  - Simulation bleibt schnell (vektorisiert)
"""

import numpy as np

# ── Parameter (Elo-Punkte) ────────────────────────────────────────────────────
FORM_DETERMINISTIC_MAX = 20.0  # Max. deterministischer Elo-Delta aus Formdifferenz
FORM_SIGMA             =  8.0  # σ für stochastisches Form-Rauschen
MARKET_SIGMA           =  5.0  # σ für Kader-Tiefe-Varianz (Squad depth)
KO_PRESSURE_SIGMA      =  4.0  # Zusätz. σ in KO-Runden (höherer Druck, mehr Varianz)
ENV_STRESS_SIGMA       =  5.0  # σ für Umwelt-/Venue-Stress-Varianz bei vollem Stress
TOTAL_CAP              = 40.0  # Harte Obergrenze für Gesamt-Context-Delta


def venue_environment_stress(altitude_m: float | None, lat: float | None) -> float:
    """Deterministischer Umwelt-/Venue-Stress eines Spielorts in [0, 1].

    Semantik (Hardening 2026-06-06): KEIN Wetter-Forecast — ein reproduzierbarer
    Klima-/Venue-Stress-Proxy aus statischen Stammdaten:
      - Höhenstress: Atmosphäre dünner ab ~1000 m (Azteca, Guadalajara, Denver)
      - Klima-/Hitzestress: WM 2026 (Juni/Juli, Nordhalbkugel) — niedrigere Breite = heißer
    Verwendung: AUSSCHLIESSLICH als Varianz-Verstärker in der Simulation (kein
    Richtungs-Bias, Mittel = 0). Der GERICHTETE Höheneffekt lebt allein im feature_adjuster
    (Prognose-Pfad) → unterschiedliche Momente & Pfade → KEIN Double-Counting.
    """
    alt = float(altitude_m or 0.0)
    altitude_stress = min(max((alt - 1000.0) / 1500.0, 0.0), 1.0)
    if lat is None:
        climate_stress = 0.0
    else:
        climate_stress = min(max((32.0 - float(lat)) / 20.0, 0.0), 1.0)
    return min(max(altitude_stress, climate_stress), 1.0)


def compute_group_context_vectorized(
    n_runs: int,
    form_home: float,
    form_away: float,
    mv_home: float,
    mv_away: float,
    env_stress: float = 0.0,
) -> np.ndarray:
    """n_runs context-Deltas für ein Gruppenspiel (vektorisiert). Positiv = Heimvorteil."""
    # 1. Deterministischer Kern (Formdifferenz)
    form_diff  = float(form_home - form_away)
    form_base  = np.clip(form_diff * FORM_DETERMINISTIC_MAX,
                         -FORM_DETERMINISTIC_MAX, FORM_DETERMINISTIC_MAX)

    # 2. Stochastisches Form-Rauschen (Tagesform, Aufstellung)
    form_noise = np.random.normal(0.0, FORM_SIGMA, n_runs)

    # 3. Marktwert-Verhältnis: Kader-Tiefe-Varianz
    mv_ratio   = max(float(mv_home), 1.0) / max(float(mv_away), 1.0)
    mv_sigma   = MARKET_SIGMA * np.log1p(abs(np.log(mv_ratio)))
    mv_noise   = np.random.normal(0.0, mv_sigma, n_runs)

    # 4. Umwelt-/Venue-Stress-Varianz (nur Streuung, kein Bias) bei extremen Spielorten
    es = min(max(float(env_stress), 0.0), 1.0)
    env_noise = np.random.normal(0.0, ENV_STRESS_SIGMA * es, n_runs) if es > 0 else 0.0

    total = form_base + form_noise + mv_noise + env_noise
    return np.clip(total, -TOTAL_CAP, TOTAL_CAP)


def compute_ko_context_scalar(
    form_home: float,
    form_away: float,
    mv_home: float,
    mv_away: float,
    stage: str = "ROUND_OF_32",
    env_stress: float = 0.0,
) -> float:
    """Einzelner context-Delta für ein KO-Spiel (zusätzliche KO-Druck-Varianz)."""
    form_diff = float(form_home - form_away)
    form_base = float(np.clip(form_diff * FORM_DETERMINISTIC_MAX,
                              -FORM_DETERMINISTIC_MAX, FORM_DETERMINISTIC_MAX))

    form_noise = float(np.random.normal(0.0, FORM_SIGMA))

    mv_ratio = max(float(mv_home), 1.0) / max(float(mv_away), 1.0)
    mv_sigma = MARKET_SIGMA * np.log1p(abs(np.log(mv_ratio)))
    mv_noise = float(np.random.normal(0.0, mv_sigma))

    ko_sigma_map = {
        "ROUND_OF_32": KO_PRESSURE_SIGMA * 0.5,
        "ROUND_OF_16": KO_PRESSURE_SIGMA * 0.75,
        "QUARTERFINAL": KO_PRESSURE_SIGMA,
        "SEMIFINAL": KO_PRESSURE_SIGMA * 1.25,
        "FINAL": KO_PRESSURE_SIGMA * 1.5,
    }
    ko_sigma = ko_sigma_map.get(stage, KO_PRESSURE_SIGMA)
    ko_noise = float(np.random.normal(0.0, ko_sigma))

    es = min(max(float(env_stress), 0.0), 1.0)
    env_noise = float(np.random.normal(0.0, ENV_STRESS_SIGMA * es)) if es > 0 else 0.0

    total = form_base + form_noise + mv_noise + ko_noise + env_noise
    return float(np.clip(total, -TOTAL_CAP, TOTAL_CAP))
