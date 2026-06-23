import json
from fastapi import APIRouter, Query

from app.database import get_pool
from app.cache import get as cache_get, set as cache_set

router = APIRouter(tags=["Search"])


def _parse(val):
    if isinstance(val, str):
        try: return json.loads(val)
        except: return {}
    return val if val else {}


@router.get("/api/v1/search")
async def search_channels(
    q: str = Query(..., min_length=1, max_length=100, description="Search query"),
    type: str | None = Query(None, alias="type", description="Filter by stream type"),
    group: str | None = Query(None, description="Filter by group"),
    limit: int = Query(20, ge=1, le=100),
):
    cache_key = f"srch:{q}:{type}:{group}:{limit}"
    cached = cache_get(cache_key)
    if cached:
        return {"success": True, "data": cached}

    conditions = ["c.is_active = TRUE"]
    params = [f"%{q}%", f"%{q}%"]
    idx = 3
    conditions.append("(c.name ILIKE $1 OR c.tvg_id ILIKE $2 OR cat.name ILIKE $1)")

    if type:
        conditions.append(f"c.stream_type = ${idx}")
        params.append(type)
        idx += 1
    if group:
        conditions.append(f"c.category_id = (SELECT id FROM categories WHERE name = ${idx})")
        params.append(group)
        idx += 1

    where = " AND ".join(conditions)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT c.id, c.tvg_id, c.name, c.logo, cat.name as gn,
                       c.url, c.stream_type, c.has_drm, c.drm_info, c.headers,
                       c.country, c.is_active
                FROM channels c LEFT JOIN categories cat ON cat.id = c.category_id
                WHERE {where}
                ORDER BY CASE WHEN c.name ILIKE $1 THEN 0 ELSE 1 END, c.name ASC
                LIMIT ${idx}""",
            *params, limit,
        )

    data = [{
        "id": r["id"], "tvg_id": r["tvg_id"], "name": r["name"],
        "logo": r["logo"], "group_name": r["gn"],
        "url": r["url"], "stream_type": r["stream_type"],
        "has_drm": r["has_drm"],
        "drm_info": _parse(r["drm_info"]),
        "headers": _parse(r["headers"]),
        "country": r["country"], "is_active": r["is_active"],
    } for r in rows]

    cache_set(cache_key, data, 20)
    return {"success": True, "data": data}
