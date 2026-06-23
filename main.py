import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
import uvicorn
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import create_pool, close_pool
from app.middleware.security import SecurityHeadersMiddleware, RateLimitMiddleware
from app.models.database import CREATE_SCHEMA_SQL
from app.routers.admin import load_data_on_startup
from app.routers import channels, categories, countries, epg, playlist, search, stats, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("istv")

IS_VERCEL = os.environ.get("VERCEL", "").lower() == "1"


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
    else:
        logger.info("Vercel mode: skipping data load at startup")

    yield

    await close_pool()
    logger.info("ISTV API shut down")


app = FastAPI(
    title="ISTV API",
    description="Free IPTV Channel API — Daftar channel TV live dari Indonesia & 27+ negara",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)

settings = get_settings()
origins = (
    ["*"]
    if settings.cors_origins == "*"
    else [o.strip() for o in settings.cors_origins.split(",")]
)

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
    from app.database import get_pool

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    return {
        "status": "ok",
        "version": "1.0.0",
        "database": db_status,
    }


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
