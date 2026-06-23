import asyncio
import logging
import os
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect, Query
import uvicorn
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import get_settings
from app.database import create_pool, close_pool, get_pool
from app.middleware.security import SecurityHeadersMiddleware, RateLimitMiddleware, AdminAuthMiddleware
from app.models.database import CREATE_SCHEMA_SQL
from app.routers.admin import load_data_on_startup
from app.routers import channels, categories, countries, epg, playlist, search, stats, admin
from app.cache import get as cache_get, set as cache_set

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("istv")

IS_VERCEL = os.environ.get("VERCEL", "").lower() == "1"

_ws_clients: set[WebSocket] = set()
_reload_task: asyncio.Task | None = None


async def _broadcast_now():
    while True:
        await asyncio.sleep(30)
        if not _ws_clients:
            continue
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT e.channel_tvg_id, e.title, e.start_time, e.end_time, c.name as ch
                       FROM epg_programs e
                       JOIN channels c ON c.tvg_id = e.channel_tvg_id AND c.is_active = TRUE
                       WHERE e.start_time <= $1 AND e.end_time > $1 AND e.title != 'Jadwal belum tersedia'
                       ORDER BY e.channel_tvg_id ASC LIMIT 100""",
                    __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                )
            data = [{
                "tvg_id": r["channel_tvg_id"],
                "title": r["title"],
                "channel": r["ch"],
            } for r in rows]
            dead = set()
            for ws in _ws_clients:
                try:
                    await ws.send_json({"type": "now", "data": data, "time": len(data)})
                except Exception:
                    dead.add(ws)
            _ws_clients -= dead
        except Exception:
            pass


async def _auto_reload():
    await asyncio.sleep(30)
    while True:
        try:
            settings = get_settings()
            if settings.m3u_url and settings.epg_url:
                result = await load_data_on_startup()
                if result:
                    logger.info(f"Auto-reload complete: {result}")
        except Exception as e:
            logger.warning(f"Auto-reload skipped: {e}")
        await asyncio.sleep(21600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting ISTV API... (vercel=%s)", IS_VERCEL)

    app.state.pool = await create_pool()
    logger.info("Database pool created")

    async with app.state.pool.acquire() as conn:
        await conn.execute(CREATE_SCHEMA_SQL)
    logger.info("Database schema ensured")

    if not IS_VERCEL:
        asyncio.create_task(load_data_on_startup())
        global _reload_task
        _reload_task = asyncio.create_task(_auto_reload())
        asyncio.create_task(_broadcast_now())
    else:
        logger.info("Vercel mode: skipping background tasks")

    yield

    if _reload_task:
        _reload_task.cancel()
    for ws in _ws_clients:
        await ws.close()
    await close_pool()
    logger.info("ISTV API shut down")


app = FastAPI(
    title="ISTV API",
    description="""
Free IPTV Channel API — 1.045+ channel TV live dari Indonesia & 27+ negara.

Dibuat oleh [IbraDecode](https://github.com/IbraDecode) · Decode Labs

## Fitur
- **1.045+ channel** live TV dari 29 negara (HLS, DASH, TS)
- **22.607+ program EPG** dengan jadwal now/next/upcoming
- **Multi-format playlist**: M3U, JSON, XML, CSV
- **Pencarian** channel + program EPG (multi-field)
- **Filter** grup, negara, tipe stream, DRM
- **Channel acak** & channel serupa
- **Cek ketersediaan stream** langsung
- **Stream proxy** — bypass CORS/geo restriction
- **WebSocket** — live now/next updates
- **Cache pintar** LRU dengan hit/miss metrics
- **Keamanan** rate limiting, security headers, API key, parameterized queries
    """,
    version="3.0.0",
    lifespan=lifespan,
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
    contact={
        "name": "IbraDecode",
        "url": "https://github.com/IbraDecode",
    },
)

settings = get_settings()
origins = (
    ["*"]
    if settings.cors_origins == "*"
    else [o.strip() for o in settings.cors_origins.split(",")]
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Total-Pages", "Retry-After"],
    max_age=3600,
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AdminAuthMiddleware)

app.include_router(channels.router)
app.include_router(categories.router)
app.include_router(countries.router)
app.include_router(epg.router)
app.include_router(playlist.router)
app.include_router(search.router)
app.include_router(stats.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    return {
        "status": "ok",
        "version": "3.0.0",
        "database": db_status,
    }


@app.get("/api/v1/channels.csv")
async def export_channels_csv(
    group: str | None = Query(None),
    type: str | None = Query(None, alias="type"),
    country: str | None = Query(None),
):
    """Export semua channel ke format CSV."""
    conditions = ["c.is_active = TRUE"]
    params = []
    idx = 1
    if group:
        conditions.append(f"c.category_id = (SELECT id FROM categories WHERE name = ${idx})")
        params.append(group); idx += 1
    if type:
        conditions.append(f"c.stream_type = ${idx}")
        params.append(type); idx += 1
    if country:
        conditions.append(f"c.country ILIKE ${idx}")
        params.append(f"%{country}%"); idx += 1

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT c.tvg_id, c.name, c.logo, cat.name as gn,
                       c.url, c.stream_type, c.has_drm, c.country
                FROM channels c LEFT JOIN categories cat ON cat.id = c.category_id
                WHERE {' AND '.join(conditions)}
                ORDER BY c.name ASC""",
            *params,
        )

    import csv, io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["tvg_id", "name", "logo", "group", "url", "type", "drm", "country"])
    for r in rows:
        w.writerow([r["tvg_id"], r["name"], r["logo"], r["gn"], r["url"], r["stream_type"], r["has_drm"], r["country"]])

    return Response(content=buf.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=channels.csv",
    })


@app.get("/api/v1/proxy")
async def stream_proxy(url: str = Query(..., description="Stream URL to proxy")):
    """Proxy stream URL untuk bypass CORS/geo restriction. Meneruskan content-type asli."""
    cache_key = f"proxy:headers:{url}"
    cached = cache_get(cache_key)
    if not cached:
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                head = await client.head(url, headers={"User-Agent": "ISTV/3.0"})
                cached = dict(head.headers)
                cache_set(cache_key, cached, 300)
        except Exception:
            cached = {}

    content_type = cached.get("content-type", "application/octet-stream")

    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "ISTV/3.0"})
            return Response(
                content=resp.content,
                media_type=content_type,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=60",
                    "Content-Length": str(len(resp.content)),
                },
            )
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={"success": False, "error": "Proxy timeout", "code": 504},
        )
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"success": False, "error": f"Proxy error: {str(e)[:80]}", "code": 502},
        )


@app.websocket("/api/v1/ws/now")
async def websocket_now(websocket: WebSocket):
    """WebSocket — terima update real-time acara yang sedang tayang setiap 30 detik."""
    await websocket.accept()
    _ws_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(websocket)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error", "code": 500},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail, "code": exc.status_code},
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )