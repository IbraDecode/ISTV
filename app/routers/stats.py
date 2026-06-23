from fastapi import APIRouter

from app.database import get_pool
from app import cache

router = APIRouter(tags=["Stats"])


@router.get("/api/v1/stats")
async def get_stats():
    cached = cache.get("stats:all")
    if cached:
        return {"success": True, "data": {**cached, "cache": cache.stats()}}

    pool = await get_pool()
    async with pool.acquire() as conn:
        total_channels = (await conn.fetchval("SELECT COUNT(*) FROM channels WHERE is_active = TRUE")) or 0
        total_categories = (await conn.fetchval("SELECT COUNT(*) FROM categories")) or 0
        total_epg = (await conn.fetchval("SELECT COUNT(*) FROM epg_programs")) or 0
        by_type = await conn.fetch(
            "SELECT stream_type, COUNT(*) as cnt FROM channels WHERE is_active = TRUE GROUP BY stream_type"
        )
        by_drm = await conn.fetch(
            "SELECT has_drm, COUNT(*) as cnt FROM channels WHERE is_active = TRUE GROUP BY has_drm"
        )
        top_cats = await conn.fetch(
            "SELECT id, name, channel_count FROM categories ORDER BY channel_count DESC LIMIT 10"
        )

    data = {
        "total_channels": total_channels,
        "total_categories": total_categories,
        "total_epg_programs": total_epg,
        "channels_by_type": {r["stream_type"]: r["cnt"] for r in by_type},
        "channels_by_drm": {str(r["has_drm"]): r["cnt"] for r in by_drm},
        "top_categories": [
            {"id": r["id"], "name": r["name"], "channel_count": r["channel_count"]}
            for r in top_cats
        ],
    }
    cache.set("stats:all", data, 60)
    return {"success": True, "data": {**data, "cache": cache.stats()}}
