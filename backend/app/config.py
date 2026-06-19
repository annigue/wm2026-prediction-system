from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://wm2026:wm2026@localhost:5432/wm2026"
    database_url_sync: str = "postgresql+psycopg2://wm2026:wm2026@localhost:5432/wm2026"
    redis_url: str = "redis://localhost:6379/0"
    admin_token: str = "wm2026-admin-token"

    monte_carlo_runs: int = 100000
    # Hinweis (Sensitivitäts-Backtest, scripts/evaluate_sensitivity.py): auf der Historie ist
    # höheres K durchgängig besser (K=20 am schlechtesten, monoton bis K=60). Bewusst NICHT
    # geändert — der Test isoliert keine Turnier-Bedingung (vorkalibrierte Start-Ratings, nur
    # 3–7 Spiele) und "Elo bleibt unverändert". Anhebung (allg. 40 / Turnier 30) nur nach
    # ausdrücklicher Freigabe + Live-Beobachtung im Kalibrierungs-Monitor. Via Env tunebar.
    elo_k_factor: float = 32.0
    elo_k_factor_tournament: float = 20.0

    # ── Gastgeber-Heimvorteil (WM 2026: USA/Kanada/Mexiko) ────────────────────
    # Gerichteter Elo-Bonus, NUR wenn ein Gastgeber in der Gruppenphase spielt
    # (dort strukturell im eigenen Land). Bildet Publikum + Vertrautheit ab
    # (Reise/Höhe sind separat im feature_adjuster → kein Double-Counting).
    # Konservativ + tunebar; KO-Phase bleibt neutral (Austragungsort dort unklar).
    host_advantage_elo: float = 55.0

    football_data_api_key: str = ""
    football_data_base_url: str = "https://api.football-data.org/v4"
    rapidapi_key: str = ""

    # API-Football (api-sports.io) — zuverlässige Ergebnis-Quelle (WM 2026, League 1)
    football_api_key: str = ""
    football_api_base: str = "https://v3.football.api-sports.io"

    # ── Betting Decision Engine ──────────────────────────────────────────────
    betting_ev_threshold: float = 0.02
    betting_min_probability: float = 0.05
    betting_market_margin: float = 0.05
    betting_market_uncertainty: float = 0.15
    betting_safe_min_prob: float = 0.60

    # ── Form Engine (Punkte + Tore + Recency, form_engine_v2) ─────────────────
    form_n_matches: int = 6
    form_decay: float = 0.82

    # ── Tipping Engine ───────────────────────────────────────────────────────
    tip_points_exact: int = 4
    tip_points_diff:  int = 3
    tip_points_tendency: int = 2
    tip_max_goals: int = 6

    # ── Odds Integration ─────────────────────────────────────────────────────
    odds_api_key: str = ""
    odds_api_base: str = "https://api.the-odds-api.com/v4"
    odds_cache_ttl: int = 900

    # ── Markt-Kalibrierung (offizielle Prognose = Modell ⊕ Markt) ─────────────
    # Log-Opinion-Pool-Gewicht des Marktes. Reines Modell bleibt für die Betting
    # Engine erhalten (Edge/EV unverändert); nur die OFFIZIELLE Prognose wird kalibriert.
    odds_blend_weight: float = 0.35
    # Adaptives Markt-Gewicht: w wird per Grid-Search auf gespielten Spielen optimiert
    # (niedrigster Brier-Score). Fällt auf odds_blend_weight zurück bei zu wenig Daten.
    adaptive_blend: bool = True
    adaptive_blend_min_matches: int = 8
    # Vertrauen-Stufen aus der max-WS der kalibrierten W/U/N
    conf_high: float = 0.55
    conf_mid: float = 0.42
    # Modell-vs-Markt-Divergenz (Total Variation) → Übereinstimmungs-Buckets
    div_confirm: float = 0.08
    div_strong: float = 0.18

    # ── Attack-/Defense-Ratings (aus historischen Ergebnissen) ────────────────
    # Relativ zum Tor-Schnitt, recency-gewichtet + Shrinkage zum Neutralwert 1.0.
    ad_window: int = 20          # letzte N Spiele je Team
    ad_decay: float = 0.90       # Recency: weight_i = decay^i
    ad_shrinkage_k: float = 8.0  # Pseudo-Spiele Richtung Neutralwert (kleine Stichprobe)
    ad_clamp_lo: float = 0.65    # Clamp gegen Ausreißer
    ad_clamp_hi: float = 1.55
    # Dämpfung des Attack/Defense-Einflusses aufs λ: (Attack·Defense)^ad_gamma.
    # Sensitivitäts-Backtest (9360 Spiele, scripts/evaluate_sensitivity.py): LogLoss/Brier/ECE
    # minimieren bei 0.7–0.85 (ECE 0.050→0.030); 0.5 war leicht zu konservativ. Auf 0.7 gesetzt —
    # spürbar bessere Kalibrierung, Elo bleibt dominant. Via AD_GAMMA-Env tunebar; 0.0 = aus.
    ad_gamma: float = 0.7


settings = Settings()

# Gastgeber der WM 2026 (Team-IDs — robust gegen abweichende Länder-Strings).
HOST_NATIONS = frozenset({"usa", "mexico", "canada"})
