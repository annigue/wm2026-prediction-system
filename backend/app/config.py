from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://wm2026:wm2026@localhost:5432/wm2026"
    database_url_sync: str = "postgresql+psycopg2://wm2026:wm2026@localhost:5432/wm2026"
    redis_url: str = "redis://localhost:6379/0"
    admin_token: str = "wm2026-admin-token"

    monte_carlo_runs: int = 100000
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


settings = Settings()

# Gastgeber der WM 2026 (Team-IDs — robust gegen abweichende Länder-Strings).
HOST_NATIONS = frozenset({"usa", "mexico", "canada"})
