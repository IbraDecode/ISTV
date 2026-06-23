import json
import asyncio
from fastapi import APIRouter, HTTPException, Query
import httpx

from app.database import get_pool
from app.models.database import TRUNCATE_SQL
from app.parser.m3u import parse_m3u
from app.parser.epg_xml import parse_epg
from app.config import get_settings
from app import cache

router = APIRouter(tags=["Admin"])

COUNTRY_MAP = {
    "TV JEPANG": "Japan", "Japan": "Japan",
    "Korea": "South Korea", "Korea Selatan": "South Korea",
    "Korean Channels": "South Korea",
    "United States": "United States", "US": "United States",
    "United Kingdom": "United Kingdom", "UK": "United Kingdom",
    "Brazil": "Brazil", "India": "India", "Thailand": "Thailand",
    "Malaysia": "Malaysia", "TV Malaysia": "Malaysia",
    "Singapore": "Singapore", "Mediacorp Singapore": "Singapore",
    "China": "China", "Turkey": "Turkey", "Turki": "Turkey",
    "Germany": "Germany", "Jerman": "Germany",
    "France": "France", "Perancis": "France",
    "Russia": "Russia", "Rusia": "Russia",
    "Italy": "Italy", "Italia": "Italy",
    "Spain": "Spain", "Spanyol": "Spain",
    "Mexico": "Mexico", "Meksiko": "Mexico",
    "Philippines": "Philippines", "Filipina": "Philippines",
    "Vietnam": "Vietnam", "Egypt": "Egypt", "Mesir": "Egypt",
    "Saudi Arabia": "Saudi Arabia",
    "Nigeria": "Nigeria", "South Africa": "South Africa",
    "Afrika Selatan": "South Africa",
    "Bangladesh": "Bangladesh", "Iran": "Iran",
    "Pakistan": "Pakistan", "Kenya": "Kenya",
    "Argentina": "Argentina", "Colombia": "Colombia",
    "Kolombia": "Colombia", "UAE & Arab": "UAE", "UAE": "UAE",
    "Indonesia": "Indonesia", "Lokal": "Indonesia",
    "Local Channels": "Indonesia",
    "Indonesia Channels": "Indonesia",
    "NASIONAL": "Indonesia",
    "TVRI GROUP": "Indonesia", "TVRI": "Indonesia",
    "TV HIBURAN": "Indonesia",
    "Bola Indonesia": "Indonesia",
    "WorldCup 2026": "International",
}


def detect_country(group_name: str) -> str:
    for key, country in COUNTRY_MAP.items():
        if key.lower() in group_name.lower():
            return country
    return ""


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
                country = detect_country(ch.group)
                await conn.execute(
                    """INSERT INTO channels
                       (tvg_id, name, logo, category_id, url, stream_type,
                        has_drm, drm_info, headers, kodiprops, country)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb,$10::jsonb,$11)""",
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
                    country,
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
    """
    Reload semua data dari source M3U & EPG URL.
    Akan menghapus data lama dan mengisi ulang.
    """
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


@router.post("/api/v1/admin/cleanup-epg")
async def cleanup_epg_placeholders():
    """
    Hapus program EPG placeholder ("Jadwal belum tersedia") dari database.
    Juga hapus duplikat program yang memiliki id sama.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            deleted = await conn.execute(
                "DELETE FROM epg_programs WHERE title = 'Jadwal belum tersedia'"
            )
            deleted = int(deleted.split()[-1])

            dedup = await conn.execute(
                """DELETE FROM epg_programs e
                   USING epg_programs d
                   WHERE e.id < d.id
                     AND e.channel_tvg_id = d.channel_tvg_id
                     AND e.title = d.title
                     AND e.start_time = d.start_time
                     AND e.end_time = d.end_time"""
            )
            dedup = int(dedup.split()[-1])

    return {
        "success": True,
        "data": {
            "deleted_placeholders": deleted,
            "deleted_duplicates": dedup,
        },
    }


@router.post("/api/v1/admin/flush-cache")
async def flush_cache():
    """Hapus semua cache in-memory."""
    cache.invalidate()
    return {"success": True, "data": {"message": "Cache flushed"}}


@router.get("/api/v1/admin/health-check")
async def mass_health_check(
    limit: int = Query(20, ge=1, le=100, description="Jumlah channel yang dicek"),
    timeout: int = Query(5, ge=1, le=10, description="Timeout per request (detik)"),
):
    """Cek ketersediaan stream untuk N channel secara acak. Report reachable/unreachable count."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT tvg_id, name, url FROM channels WHERE is_active = TRUE AND has_drm = FALSE ORDER BY RANDOM() LIMIT $1",
            limit,
        )

    results = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout), follow_redirects=True) as client:
        for r in rows:
            try:
                resp = await client.head(r["url"], headers={"User-Agent": "ISTV/3.0"})
                ok = resp.status_code < 500
                results.append({"tvg_id": r["tvg_id"], "name": r["name"], "reachable": ok, "status": resp.status_code})
            except Exception as e:
                results.append({"tvg_id": r["tvg_id"], "name": r["name"], "reachable": False, "error": str(e)[:60]})

    reachable = sum(1 for r in results if r["reachable"])
    return {
        "success": True,
        "data": {
            "checked": len(results),
            "reachable": reachable,
            "unreachable": len(results) - reachable,
            "details": results,
        },
    }
