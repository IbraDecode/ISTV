import time
import logging
from typing import Any

logger = logging.getLogger("istv")

_cache: dict[str, tuple[float, Any]] = {}
_ttl: dict[str, int] = {}


def set(key: str, value: Any, ttl_seconds: int = 30):
    _cache[key] = (time.time(), value)
    _ttl[key] = ttl_seconds


def get(key: str) -> Any | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, value = entry
    ttl = _ttl.get(key, 30)
    if time.time() - ts > ttl:
        del _cache[key]
        return None
    return value


def invalidate(key: str = None):
    if key:
        _cache.pop(key, None)
    else:
        _cache.clear()


def cleanup():
    now = time.time()
    expired = [k for k, (ts, _) in _cache.items() if now - ts > _ttl.get(k, 30)]
    for k in expired:
        del _cache[k]
    if expired:
        logger.debug(f"Cache cleanup: removed {len(expired)} expired entries")
