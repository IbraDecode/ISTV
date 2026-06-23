import json
import math
from fastapi import APIRouter, Query, HTTPException

from app.database import get_pool
from app.cache import get as cache_get, set as cache_set

router = APIRouter(tags=["Categories"])


def _parse(val):
    if isinstance(val, str):
        try: return json.loads(val)
        except: return {}
    return val if val else {}


@router.get("/api/v1/categories")
async def list_categories():
    cached = cache_get("cats:all")
    if cached:
        return {"success": True, "data": cached}

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, channel_count FROM categories ORDER BY channel_count DESC"
        )

    data = [{"id": r["id"], "name": r["name"], "channel_count": r["channel_count"]} for r in rows]
    cache_set("cats:all", data, 60)
    return {"success": True, "data": data}


@router.get("/api/v1/categories/{name}/channels")
async def get_category_channels(
    name: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        cat = await conn.fetchrow("SELECT id FROM categories WHERE name = $1", name)
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")

        total = (await conn.fetchval(
            "SELECT COUNT(*) FROM channels WHERE category_id = $1 AND is_active = TRUE",
            cat["id"],
        )) or 0

        total_pages = max(1, math.ceil(total / limit))
        offset = (page - 1) * limit

        rows = await conn.fetch(
            """SELECT c.id, c.tvg_id, c.name, c.logo, cat.name as gn,
                      c.url, c.stream_type, c.has_drm, c.drm_info, c.headers,
                      c.country, c.is_active
               FROM channels c LEFT JOIN categories cat ON cat.id = c.category_id
               WHERE c.category_id = $1 AND c.is_active = TRUE
               ORDER BY c.name ASC LIMIT $2 OFFSET $3""",
            cat["id"], limit, offset,
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

    return {
        "success": True, "data": data,
        "pagination": {"page": page, "limit": limit, "total": total, "total_pages": total_pages},
    }
