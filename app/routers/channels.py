import math
import json
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Query, HTTPException

from app.database import get_pool
from app.cache import get as cache_get, set as cache_set
from app.helpers import row_to_channel_dict, get_now_program, get_next_program
from app.schemas.responses import ApiResponse, Pagination, ChannelOut

router = APIRouter(tags=["Channels"])


def _parse(val):
    if isinstance(val, str):
        try: return json.loads(val)
        except: return {}
    return val if val else {}


@router.get("/api/v1/channels", response_model=ApiResponse)
async def list_channels(
    group: Optional[str] = Query(None, description="Filter by group/category"),
    type: Optional[str] = Query(None, alias="type", description="Stream type: hls, dash"),
    has_drm: Optional[bool] = Query(None, description="Filter by DRM status"),
    country: Optional[str] = Query(None, description="Filter by country"),
    search: Optional[str] = Query(None, description="Search by name"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
):
    cache_key = f"ch:l:{group}:{type}:{has_drm}:{country}:{search}:{page}:{limit}"
    cached = cache_get(cache_key)
    if cached:
        return ApiResponse(**cached)

    conditions = ["c.is_active = TRUE"]
    params = []
    idx = 1

    if group:
        conditions.append(f"c.category_id = (SELECT id FROM categories WHERE name = ${idx})")
        params.append(group)
        idx += 1
    if type:
        conditions.append(f"c.stream_type = ${idx}")
        params.append(type)
        idx += 1
    if has_drm is not None:
        conditions.append(f"c.has_drm = ${idx}")
        params.append(has_drm)
        idx += 1
    if country:
        conditions.append(f"c.country ILIKE ${idx}")
        params.append(f"%{country}%")
        idx += 1
    if search:
        conditions.append(f"c.name ILIKE ${idx}")
        params.append(f"%{search}%")
        idx += 1

    where = " AND ".join(conditions)

    pool = await get_pool()
    async with pool.acquire() as conn:
        total = (await conn.fetchval(f"SELECT COUNT(*) FROM channels c WHERE {where}", *params)) or 0
        total_pages = max(1, math.ceil(total / limit))
        offset = (page - 1) * limit
        rows = await conn.fetch(
            f"""SELECT c.id, c.tvg_id, c.name, c.logo, cat.name as gn,
                       c.url, c.stream_type, c.has_drm, c.drm_info, c.headers,
                       c.country, c.is_active
                FROM channels c LEFT JOIN categories cat ON cat.id = c.category_id
                WHERE {where}
                ORDER BY c.name ASC
                LIMIT ${idx} OFFSET ${idx + 1}""",
            *params, limit, offset,
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

    result = {
        "success": True, "data": data,
        "pagination": {"page": page, "limit": limit, "total": total, "total_pages": total_pages},
    }
    cache_set(cache_key, result, 15)
    return ApiResponse(**result)


@router.get("/api/v1/channels/random", response_model=ApiResponse)
async def get_random_channels(
    limit: int = Query(5, ge=1, le=50, description="Number of random channels"),
    group: Optional[str] = Query(None, description="Filter by group/category"),
    type: Optional[str] = Query(None, alias="type", description="Stream type: hls, dash"),
):
    cache_key = f"ch:rand:{limit}:{group}:{type}"
    cached = cache_get(cache_key)
    if cached:
        return ApiResponse(**cached)

    conditions = ["c.is_active = TRUE"]
    params = []
    idx = 1

    if group:
        conditions.append(f"c.category_id = (SELECT id FROM categories WHERE name = ${idx})")
        params.append(group)
        idx += 1
    if type:
        conditions.append(f"c.stream_type = ${idx}")
        params.append(type)
        idx += 1

    where = " AND ".join(conditions)

    pool = await get_pool()
    async with pool.acquire() as conn:
        ids = await conn.fetch(
            f"SELECT id FROM channels c WHERE {where} ORDER BY RANDOM() LIMIT ${idx}",
            *params, limit,
        )
        if not ids:
            return ApiResponse(success=True, data=[])

        placeholders = ", ".join(f"${i+1}" for i in range(len(ids)))
        id_list = [r["id"] for r in ids]
        rows = await conn.fetch(
            f"""SELECT c.id, c.tvg_id, c.name, c.logo, cat.name as gn,
                       c.url, c.stream_type, c.has_drm, c.drm_info, c.headers,
                       c.country, c.is_active
                FROM channels c LEFT JOIN categories cat ON cat.id = c.category_id
                WHERE c.id IN ({placeholders})
                ORDER BY c.name ASC""",
            *id_list,
        )

        now = datetime.now(timezone.utc)

        data = []
        for r in rows:
            d = {
                "id": r["id"], "tvg_id": r["tvg_id"], "name": r["name"],
                "logo": r["logo"], "group_name": r["gn"],
                "url": r["url"], "stream_type": r["stream_type"],
                "has_drm": r["has_drm"],
                "drm_info": _parse(r["drm_info"]),
                "headers": _parse(r["headers"]),
                "country": r["country"], "is_active": r["is_active"],
            }
            epg_row = await conn.fetchrow(
                """SELECT title, start_time, end_time
                   FROM epg_programs
                   WHERE channel_tvg_id = $1 AND start_time <= $2 AND end_time > $2
                   LIMIT 1""",
                r["tvg_id"], now,
            )
            d["epg_now"] = {
                "title": epg_row["title"],
                "start_time": epg_row["start_time"].isoformat(),
                "end_time": epg_row["end_time"].isoformat(),
            } if epg_row else None
            data.append(d)

    result = {"success": True, "data": data}
    cache_set(cache_key, result, 3600)
    return ApiResponse(**result)


@router.get("/api/v1/channels/{tvg_id}", response_model=ApiResponse)
async def get_channel(tvg_id: str):
    cache_key = f"ch:d:{tvg_id}"
    cached = cache_get(cache_key)
    if cached:
        return ApiResponse(**cached)

    pool = await get_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            """SELECT c.id, c.tvg_id, c.name, c.logo, cat.name as gn,
                      c.url, c.stream_type, c.has_drm, c.drm_info, c.headers,
                      c.country, c.is_active
               FROM channels c LEFT JOIN categories cat ON cat.id = c.category_id
               WHERE c.tvg_id = $1 AND c.is_active = TRUE""",
            tvg_id,
        )
    if not r:
        raise HTTPException(status_code=404, detail="Channel not found")

    data = {
        "id": r["id"], "tvg_id": r["tvg_id"], "name": r["name"],
        "logo": r["logo"], "group_name": r["gn"],
        "url": r["url"], "stream_type": r["stream_type"],
        "has_drm": r["has_drm"],
        "drm_info": _parse(r["drm_info"]),
        "headers": _parse(r["headers"]),
        "country": r["country"], "is_active": r["is_active"],
        "epg_now": await get_now_program(tvg_id),
        "epg_next": await get_next_program(tvg_id),
    }

    result = {"success": True, "data": data}
    cache_set(cache_key, result, 15)
    return ApiResponse(**result)


@router.get("/api/v1/channels/{tvg_id}/stream", response_model=ApiResponse)
async def get_channel_stream(tvg_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            """SELECT url, headers, has_drm, drm_info, stream_type
               FROM channels WHERE tvg_id = $1 AND is_active = TRUE""",
            tvg_id,
        )
    if not r:
        raise HTTPException(status_code=404, detail="Channel not found")

    return ApiResponse(success=True, data={
        "url": r["url"],
        "headers": _parse(r["headers"]),
        "has_drm": r["has_drm"],
        "drm_info": _parse(r["drm_info"]),
        "type": r["stream_type"],
    })


@router.get("/api/v1/channels/{tvg_id}/similar", response_model=ApiResponse)
async def get_similar_channels(
    tvg_id: str,
    limit: int = Query(10, ge=1, le=50, description="Number of similar channels"),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        channel = await conn.fetchrow(
            "SELECT id, category_id FROM channels WHERE tvg_id = $1 AND is_active = TRUE",
            tvg_id,
        )
        if not channel or not channel["category_id"]:
            return ApiResponse(success=True, data=[])

        rows = await conn.fetch(
            """SELECT c.id, c.tvg_id, c.name, c.logo, cat.name as gn,
                      c.url, c.stream_type, c.has_drm, c.drm_info, c.headers,
                      c.country, c.is_active
               FROM channels c LEFT JOIN categories cat ON cat.id = c.category_id
               WHERE c.category_id = $1 AND c.tvg_id != $2 AND c.is_active = TRUE
               ORDER BY RANDOM()
               LIMIT $3""",
            channel["category_id"], tvg_id, limit,
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

    return ApiResponse(success=True, data=data)
