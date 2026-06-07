"""
Odds Provider — holt echte Marktquoten von The Odds API.

Graceful Degradation:
  - Kein API-Key → None (BDE nutzt dann fair-odds-Schätzung)
  - API nicht erreichbar / Rate-Limit → letzte bekannte Quoten (last-known) statt None
  - In-Memory-Cache mit TTL reduziert API-Calls

The Odds API: https://the-odds-api.com  ·  Sportkey: 'soccer_fifa_world_cup'
"""

from __future__ import annotations
import re
import time
import unicodedata
import httpx
from app.config import settings

_SPORT_KEY = "soccer_fifa_world_cup"
_BASE = settings.odds_api_base

# In-Memory-Cache: {cache_key: (timestamp, data)}
_cache: dict[str, tuple[float, list]] = {}
# "Last known good" — überlebt das TTL und dient als Fallback bei API-Ausfall.
_last_good: dict[str, tuple[float, list]] = {}


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and (time.time() - entry[0]) < settings.odds_cache_ttl:
        return entry[1]
    return None


def _cache_set(key: str, data: list):
    _cache[key] = (time.time(), data)
    _last_good[key] = (time.time(), data)


def _stale_fallback(key: str):
    """Letzte bekannte Quoten (auch nach TTL) — Fallback bei API-Fehler/Rate-Limit."""
    entry = _last_good.get(key)
    return entry[1] if entry else None


def last_good_age_seconds(key: str = "h2h") -> float | None:
    """Alter der letzten erfolgreich abgerufenen Quoten in Sekunden (Monitoring)."""
    entry = _last_good.get(key)
    return round(time.time() - entry[0], 1) if entry else None


def is_available() -> bool:
    """True wenn ein Odds-API-Key konfiguriert ist."""
    return bool(settings.odds_api_key)


def fetch_h2h_odds() -> list | None:
    """Holt 1X2 + Totals aller WM-Spiele. None bei kein Key; Fallback bei Fehler."""
    if not settings.odds_api_key:
        return None

    cached = _cache_get("h2h")
    if cached is not None:
        return cached

    try:
        r = httpx.get(
            f"{_BASE}/sports/{_SPORT_KEY}/odds",
            params={
                "apiKey":     settings.odds_api_key,
                "regions":    "eu",
                "markets":    "h2h,totals",
                "oddsFormat": "decimal",
            },
            timeout=15,
        )
        if r.status_code != 200:
            return _stale_fallback("h2h")
        data = r.json()
        _cache_set("h2h", data)
        return data
    except Exception:
        return _stale_fallback("h2h")


def find_match_odds(home_name: str, away_name: str) -> dict | None:
    """Quoten für ein konkretes Spiel anhand der Teamnamen (englisch erwartet)."""
    games = fetch_h2h_odds()
    if not games:
        return None

    for game in games:
        gh = game.get("home_team", "")
        ga = game.get("away_team", "")
        if not (_name_match(home_name, gh) and _name_match(away_name, ga)):
            continue

        result: dict[str, float] = {}
        for bm in game.get("bookmakers", []):
            for market in bm.get("markets", []):
                if market["key"] == "h2h":
                    for o in market["outcomes"]:
                        nm = o["name"]
                        if _name_match(home_name, nm):
                            result.setdefault("home", o["price"])
                        elif _name_match(away_name, nm):
                            result.setdefault("away", o["price"])
                        elif nm.lower() == "draw":
                            result.setdefault("draw", o["price"])
                elif market["key"] == "totals":
                    for o in market["outcomes"]:
                        if o.get("point") == 2.5:
                            if o["name"].lower() == "over":
                                result.setdefault("over25", o["price"])
                            elif o["name"].lower() == "under":
                                result.setdefault("under25", o["price"])
            if "home" in result and "draw" in result and "away" in result:
                break
        return result or None

    return None


# Aliase: kanonische Form für Schreibweisen, die zwischen DB (home_country, EN) und
# Odds-Feed differieren und nicht per Teilstring matchen.
_NAME_ALIASES = {
    "united states": "usa",
    "usa":           "usa",
    "korea republic": "south korea",
    "republic of korea": "south korea",
    "ir iran":       "iran",
    "china pr":      "china",
}


def _norm_name(s: str) -> str:
    """Akzent-/Satzzeichen-unabhängige Normalform (NFKD, ASCII, lowercase)."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    return _NAME_ALIASES.get(s, s)


def _name_match(a: str, b: str) -> bool:
    """Toleranter Namensvergleich: normalisiert + Gleichheit oder Teilstring beidseitig."""
    ca, cb = _norm_name(a), _norm_name(b)
    if not ca or not cb:
        return False
    return ca == cb or ca in cb or cb in ca
