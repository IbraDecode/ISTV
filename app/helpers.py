import json
from datetime import datetime, timezone
from typing import Any

from app.database import get_pool
from app.cache import get as cache_get, set as cache_set


def _parse_json(val: Any) -> Any:
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return {}
    return val if val else {}


CHANNEL_FIELDS = """c.id, c.tvg_id, c.name, c.logo, cat.name as group_name,
   c.url, c.stream_type, c.has_drm, c.drm_info, c.headers,
   c.country, c.is_active"""


def row_to_channel_dict(r) -> dict:
    return {
        "id": r["id"],
        "tvg_id": r["tvg_id"],
        "name": r["name"],
        "logo": r["logo"],
        "group_name": r["group_name"],
        "url": r["url"],
        "stream_type": r["stream_type"],
        "has_drm": r["has_drm"],
        "drm_info": _parse_json(r["drm_info"]),
        "headers": _parse_json(r["headers"]),
        "country": r["country"],
        "is_active": r["is_active"],
    }


async def get_now_program(tvg_id: str) -> dict | None:
    now = datetime.now(timezone.utc)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, channel_tvg_id, title, description,
                      start_time, end_time, category
               FROM epg_programs
                WHERE channel_tvg_id = $1 AND start_time <= $2 AND end_time > $2
                  AND title != 'Jadwal belum tersedia'
                LIMIT 1""",
            tvg_id,
            now,
        )
    if not row:
        return None
    return {
        "id": row["id"],
        "channel_tvg_id": row["channel_tvg_id"],
        "title": row["title"],
        "description": row["description"],
        "start_time": row["start_time"].isoformat(),
        "end_time": row["end_time"].isoformat(),
        "category": row["category"],
    }


async def get_next_program(tvg_id: str) -> dict | None:
    now = datetime.now(timezone.utc)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, channel_tvg_id, title, description,
                      start_time, end_time, category
               FROM epg_programs
                WHERE channel_tvg_id = $1 AND start_time > $2
                  AND title != 'Jadwal belum tersedia'
                ORDER BY start_time ASC
                LIMIT 1""",
            tvg_id,
            now,
        )
    if not row:
        return None
    return {
        "id": row["id"],
        "channel_tvg_id": row["channel_tvg_id"],
        "title": row["title"],
        "description": row["description"],
        "start_time": row["start_time"].isoformat(),
        "end_time": row["end_time"].isoformat(),
        "category": row["category"],
    }
