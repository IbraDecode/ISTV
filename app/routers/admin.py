import json
from fastapi import APIRouter, HTTPException
import httpx

from app.database import get_pool
from app.models.database import TRUNCATE_SQL
from app.parser.m3u import parse_m3u
from app.parser.epg_xml import parse_epg
from app.config import get_settings

router = APIRouter(tags=["Admin"])


async def _load_data_into_db(m3u_text: str, epg_text: str) -> dict:
    channels = parse_m3u(m3u_text)
    programs = parse_epg(epg_text)

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(TRUNCATE_SQL)

            cat_map = {}
            for ch in channels:
                if ch.group not in cat_map:
                    row = await conn.fetchrow(
                        "INSERT INTO categories (name) VALUES ($1) ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name RETURNING id",
                        ch.group,
                    )
                    cat_map[ch.group] = row["id"]

            for ch in channels:
                cat_id = cat_map.get(ch.group)
                await conn.execute(
                    """INSERT INTO channels
                       (tvg_id, name, logo, category_id, url, stream_type, has_drm, drm_info, headers, kodiprops)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb,$10::jsonb)""",
                    ch.tvg_id,
                    ch.name,
                    ch.logo,
                    cat_id,
                    ch.url,
                    ch.stream_type,
                    ch.has_drm,
                    json.dumps(ch.drm_info) if ch.drm_info else None,
                    json.dumps(ch.headers) if ch.headers else "{}",
                    json.dumps(ch.kodiprops) if ch.kodiprops else "{}",
                )

            for cat_name, cat_id in cat_map.items():
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM channels WHERE category_id = $1",
                    cat_id,
                )
                await conn.execute(
                    "UPDATE categories SET channel_count = $1 WHERE id = $2",
                    count,
                    cat_id,
                )

            batch = []
            for p in programs:
                batch.append(
                    (p.channel_tvg_id, p.title, p.description, p.start_time, p.end_time, p.category)
                )
                if len(batch) >= 500:
                    await conn.executemany(
                        """INSERT INTO epg_programs
                           (channel_tvg_id, title, description, start_time, end_time, category)
                           VALUES ($1,$2,$3,$4,$5,$6)""",
                        batch,
                    )
                    batch = []
            if batch:
                await conn.executemany(
                    """INSERT INTO epg_programs
                       (channel_tvg_id, title, description, start_time, end_time, category)
                       VALUES ($1,$2,$3,$4,$5,$6)""",
                    batch,
                )

    return {
        "channels_loaded": len(channels),
        "programs_loaded": len(programs),
        "categories_loaded": len(cat_map),
    }


async def load_data_on_startup():
    import logging
    logger = logging.getLogger("istv")

    settings = get_settings()
    if not settings.m3u_url or not settings.epg_url:
        return None

    pool = await get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM channels")
        if count and count > 0:
            logger.info(f"Data already loaded ({count} channels), skipping startup load")
            return None

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            m3u_resp = await client.get(settings.m3u_url)
            epg_resp = await client.get(settings.epg_url)

        if m3u_resp.status_code != 200 or epg_resp.status_code != 200:
            logger.warning(f"Data fetch failed: M3U={m3u_resp.status_code}, EPG={epg_resp.status_code}")
            return None

        result = await _load_data_into_db(m3u_resp.text, epg_resp.text)
        logger.info(
            f"Loaded {result['channels_loaded']} channels, "
            f"{result['programs_loaded']} EPG programs, "
            f"{result['categories_loaded']} categories"
        )
        return result
    except Exception as e:
        logger.warning(f"Startup data load skipped: {e}")
        return None


@router.post("/api/v1/admin/reload")
async def reload_data():
    settings = get_settings()
    if not settings.m3u_url or not settings.epg_url:
        raise HTTPException(status_code=400, detail="M3U_URL or EPG_URL not configured")

    async with httpx.AsyncClient(timeout=120.0) as client:
        m3u_resp = await client.get(settings.m3u_url)
        epg_resp = await client.get(settings.epg_url)
        if m3u_resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"M3U fetch failed: {m3u_resp.status_code}",
            )
        if epg_resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"EPG fetch failed: {epg_resp.status_code}",
            )

    result = await _load_data_into_db(m3u_resp.text, epg_resp.text)
    return {"success": True, "data": result}
