"""
Redis-Cache mit Graceful Degradation.

Cached teure, deterministische Berechnungen (Projektion, aggregierte Bets).
Fällt still auf "kein Cache" zurück, wenn Redis nicht erreichbar ist —
das System funktioniert immer, Cache ist reine Performance-Optimierung.
"""

from __future__ import annotations
import json
from typing import Optional, Callable, Any

from app.config import settings

_redis = None
_redis_tried = False


def _client():
    """Lazy Redis-Verbindung. None wenn nicht verfügbar."""
    global _redis, _redis_tried
    if _redis_tried:
        return _redis
    _redis_tried = True
    try:
        import redis
        client = redis.from_url(settings.redis_url, socket_connect_timeout=1,
                                socket_timeout=1, decode_responses=True)
        client.ping()
        _redis = client
    except Exception:
        _redis = None
    return _redis


def get_json(key: str) -> Optional[Any]:
    c = _client()
    if not c:
        return None
    try:
        raw = c.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def set_json(key: str, value: Any, ttl: int = 1800) -> None:
    c = _client()
    if not c:
        return
    try:
        c.setex(key, ttl, json.dumps(value))
    except Exception:
        pass


def invalidate(prefix: str = "wm2026:") -> int:
    """Löscht alle Cache-Keys mit gegebenem Prefix. Gibt Anzahl zurück."""
    c = _client()
    if not c:
        return 0
    try:
        keys = list(c.scan_iter(match=f"{prefix}*"))
        if keys:
            c.delete(*keys)
        return len(keys)
    except Exception:
        return 0


def cached(key: str, ttl: int, producer: Callable[[], Any]) -> Any:
    """Cache-Aside-Helfer: liefert gecachten Wert oder berechnet + speichert."""
    hit = get_json(key)
    if hit is not None:
        return hit
    value = producer()
    set_json(key, value, ttl)
    return value
