import asyncpg
from app.config import get_settings

pool: asyncpg.Pool | None = None


async def create_pool() -> asyncpg.Pool:
    settings = get_settings()
    pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=2,
        max_size=10,
        command_timeout=30,
        ssl="require",
    )
    return pool


async def get_pool() -> asyncpg.Pool:
    global pool
    if pool is None:
        pool = await create_pool()
    return pool


async def close_pool():
    global pool
    if pool:
        await pool.close()
        pool = None
