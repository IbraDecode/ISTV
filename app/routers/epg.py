from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timezone

from app.database import get_pool
from app.cache import get as cache_get, set as cache_set
from app.schemas.responses import ApiResponse, ProgramOut

router = APIRouter(tags=["EPG"])


@router.get("/api/v1/epg", response_model=ApiResponse)
async def list_epg(
    channel: str | None = Query(None, description="Filter by channel tvg_id"),
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
):
    cache_key = f"epg:l:{channel}:{date}:{page}:{limit}"
    cached = cache_get(cache_key)
    if cached:
        return ApiResponse(**cached)

    conditions = []
    params = []
    idx = 1
    if channel:
        conditions.append(f"channel_tvg_id = ${idx}")
        params.append(channel)
        idx += 1
    if date:
        conditions.append(f"start_time::date = ${idx}::date")
        params.append(date)
        idx += 1

    where = " AND " + " AND ".join(conditions) if conditions else ""

    pool = await get_pool()
    async with pool.acquire() as conn:
        total = (await conn.fetchval(f"SELECT COUNT(*) FROM epg_programs{where}", *params)) or 0
        offset = (page - 1) * limit
        rows = await conn.fetch(
            f"""SELECT id, channel_tvg_id, title, description,
                       start_time, end_time, category
                FROM epg_programs{where}
                ORDER BY start_time ASC
                LIMIT ${idx} OFFSET ${idx + 1}""",
            *params, limit, offset,
        )

    programs = [{
        "id": r["id"], "channel_tvg_id": r["channel_tvg_id"],
        "title": r["title"], "description": r["description"],
        "start_time": r["start_time"].isoformat(),
        "end_time": r["end_time"].isoformat(),
        "category": r["category"],
    } for r in rows]

    result = {"success": True, "data": programs}
    cache_set(cache_key, result, 20)
    return ApiResponse(**result)


@router.get("/api/v1/epg/now", response_model=ApiResponse)
async def get_now_playing(limit: int = Query(50, ge=1, le=200)):
    now = datetime.now(timezone.utc)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT e.id, e.channel_tvg_id, e.title, e.description,
                      e.start_time, e.end_time, e.category
               FROM epg_programs e
               JOIN channels c ON c.tvg_id = e.channel_tvg_id AND c.is_active = TRUE
               WHERE e.start_time <= $1 AND e.end_time > $1
               ORDER BY e.channel_tvg_id ASC
               LIMIT $2""",
            now, limit,
        )

    programs = [{
        "id": r["id"], "channel_tvg_id": r["channel_tvg_id"],
        "title": r["title"], "description": r["description"],
        "start_time": r["start_time"].isoformat(),
        "end_time": r["end_time"].isoformat(),
        "category": r["category"],
    } for r in rows]

    return ApiResponse(success=True, data=programs)


@router.get("/api/v1/epg/now/{tvg_id}", response_model=ApiResponse)
async def get_channel_now(tvg_id: str):
    now = datetime.now(timezone.utc)
    pool = await get_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            """SELECT id, channel_tvg_id, title, description,
                      start_time, end_time, category
               FROM epg_programs
               WHERE channel_tvg_id = $1 AND start_time <= $2 AND end_time > $2
               LIMIT 1""",
            tvg_id, now,
        )
    if not r:
        return ApiResponse(success=True, data=None)

    return ApiResponse(success=True, data={
        "id": r["id"], "channel_tvg_id": r["channel_tvg_id"],
        "title": r["title"], "description": r["description"],
        "start_time": r["start_time"].isoformat(),
        "end_time": r["end_time"].isoformat(),
        "category": r["category"],
    })


@router.get("/api/v1/epg/search", response_model=ApiResponse)
async def search_epg(
    q: str = Query(..., min_length=1, max_length=200, description="Search program title"),
    channel: str | None = Query(None, description="Filter by channel tvg_id"),
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
    limit: int = Query(20, ge=1, le=100),
):
    pool = await get_pool()
    conditions = ["e.title ILIKE $1"]
    params = [f"%{q}%"]
    idx = 2

    if channel:
        conditions.append(f"e.channel_tvg_id = ${idx}")
        params.append(channel)
        idx += 1
    if date:
        conditions.append(f"e.start_time::date = ${idx}::date")
        params.append(date)
        idx += 1

    where = " AND ".join(conditions)
    params.append(limit)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT e.id, e.channel_tvg_id, e.title, e.description,
                       e.start_time, e.end_time, e.category,
                       c.name as channel_name
                FROM epg_programs e
                LEFT JOIN channels c ON c.tvg_id = e.channel_tvg_id
                WHERE {where}
                ORDER BY e.start_time ASC
                LIMIT ${idx}""",
            *params,
        )

    programs = [{
        "id": r["id"], "channel_tvg_id": r["channel_tvg_id"],
        "title": r["title"], "description": r["description"],
        "start_time": r["start_time"].isoformat(),
        "end_time": r["end_time"].isoformat(),
        "category": r["category"],
        "channel_name": r["channel_name"],
    } for r in rows]

    return ApiResponse(success=True, data=programs)


@router.get("/api/v1/epg/{tvg_id}", response_model=ApiResponse)
async def get_channel_epg(
    tvg_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    now = datetime.now(timezone.utc)
    pool = await get_pool()
    async with pool.acquire() as conn:
        total = (await conn.fetchval(
            "SELECT COUNT(*) FROM epg_programs WHERE channel_tvg_id = $1 AND end_time > $2",
            tvg_id, now,
        )) or 0
        offset = (page - 1) * limit
        rows = await conn.fetch(
            """SELECT id, channel_tvg_id, title, description,
                      start_time, end_time, category
                FROM epg_programs
                WHERE channel_tvg_id = $1 AND end_time > $2
                ORDER BY start_time ASC
                 LIMIT $3 OFFSET $4""",
             tvg_id, now, limit, offset,
        )

    programs = [{
        "id": r["id"], "channel_tvg_id": r["channel_tvg_id"],
        "title": r["title"], "description": r["description"],
        "start_time": r["start_time"].isoformat(),
        "end_time": r["end_time"].isoformat(),
        "category": r["category"],
    } for r in rows]

    return ApiResponse(success=True, data=programs)
