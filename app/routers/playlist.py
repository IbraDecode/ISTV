import json
from fastapi import APIRouter, Query, Response
from typing import Optional

from app.database import get_pool

router = APIRouter(tags=["Playlist"])


def _parse(val):
    if isinstance(val, str):
        try: return json.loads(val)
        except: return {}
    return val if val else {}


@router.get("/api/v1/playlist.m3u")
async def get_playlist(
    group: Optional[str] = Query(None, description="Filter by group"),
    type: Optional[str] = Query(None, alias="type", description="Stream type: hls, dash"),
    ott: Optional[bool] = Query(False, description="OTT mode: exclude DRM channels"),
    limit: int = Query(0, ge=0, le=5000, description="Max channels (0 = all)"),
):
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
    if ott:
        conditions.append("c.has_drm = FALSE")

    where = " AND ".join(conditions)
    limit_clause = f"LIMIT ${idx}" if limit > 0 else ""
    if limit > 0:
        params.append(limit)

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT c.tvg_id, c.name, c.logo, cat.name as gn,
                       c.url, c.stream_type, c.headers, c.kodiprops, c.has_drm
                FROM channels c LEFT JOIN categories cat ON cat.id = c.category_id
                WHERE {where}
                ORDER BY cat.name ASC, c.name ASC
                {limit_clause}""",
            *params,
        )

    lines = ['#EXTM3U url-tvg=""']
    for r in rows:
        kodiprops = _parse(r["kodiprops"])
        headers = _parse(r["headers"])

        for k, v in kodiprops.items():
            lines.append(f"#KODIPROP:{k}={v}")

        for k, v in headers.items():
            hkey = {
                "Referer": "http-referrer", "referer": "http-referrer",
                "User-Agent": "http-user-agent", "user-agent": "http-user-agent",
                "Origin": "http-origin", "origin": "http-origin",
            }.get(k)
            if hkey:
                lines.append(f"#EXTVLCOPT:{hkey}={v}")

        lines.append(
            f'#EXTINF:-1 tvg-id="{r["tvg_id"] or ""}" '
            f'tvg-logo="{r["logo"] or ""}" '
            f'group-title="{r["gn"] or "Lainnya"}",'
            f'{r["name"] or "Unknown"}'
        )
        lines.append(r["url"])

    content = "\n".join(lines) + "\n"
    return Response(
        content=content,
        media_type="audio/x-mpegurl",
        headers={
            "Content-Disposition": "attachment; filename=istv-playlist.m3u",
            "Cache-Control": "public, max-age=600",
        },
    )
