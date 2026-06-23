import time
import logging
from typing import Any

logger = logging.getLogger("istv")

_cache: dict[str, tuple[float, Any]] = {}
_ttl: dict[str, int] = {}
_access: dict[str, float] = {}
_hits: int = 0
_misses: int = 0
MAX_SIZE = 500


def set(key: str, value: Any, ttl_seconds: int = 30):
    if key not in _cache and len(_cache) >= MAX_SIZE:
        _evict_lru()
    _cache[key] = (time.time(), value)
    _ttl[key] = ttl_seconds
    _access[key] = time.time()


def get(key: str) -> Any | None:
    global _hits, _misses
    entry = _cache.get(key)
    if entry is None:
        _misses += 1
        return None
    ts, value = entry
    ttl = _ttl.get(key, 30)
    if time.time() - ts > ttl:
        del _cache[key]
        del _access[key]
        _misses += 1
        return None
    _hits += 1
    _access[key] = time.time()
    return value


def stats():
    return {
        "size": len(_cache),
        "max_size": MAX_SIZE,
        "hits": _hits,
        "misses": _misses,
        "hit_ratio": round(_hits / (_hits + _misses), 4) if (_hits + _misses) > 0 else 0,
    }


def invalidate(key: str = None):
    if key:
        _cache.pop(key, None)
        _access.pop(key, None)
    else:
        _cache.clear()
        _access.clear()


def cleanup():
    global _hits, _misses
    now = time.time()
    expired = [k for k, (ts, _) in _cache.items() if now - ts > _ttl.get(k, 30)]
    for k in expired:
        del _cache[k]
        _access.pop(k, None)
    if expired:
        logger.debug(f"Cache cleanup: removed {len(expired)} expired entries")


def _evict_lru():
    if not _access:
        return
    oldest = min(_access, key=_access.get)
    del _cache[oldest]
    del _ttl[oldest]
    del _access[oldest]
