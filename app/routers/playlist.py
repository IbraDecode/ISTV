import json
import hashlib
from fastapi import APIRouter, Query, Response, Request
from typing import Optional

from app.database import get_pool
from app.cache import get as cache_get, set as cache_set

router = APIRouter(tags=["Playlist"])


def _parse(val):
    if isinstance(val, str):
        try: return json.loads(val)
        except: return {}
    return val if val else {}


async def _fetch_channels(group=None, type=None, ott=False, limit=0):
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
        return await conn.fetch(
            f"""SELECT c.tvg_id, c.name, c.logo, cat.name as gn,
                       c.url, c.stream_type, c.headers, c.kodiprops, c.has_drm
                FROM channels c LEFT JOIN categories cat ON cat.id = c.category_id
                WHERE {where}
                ORDER BY cat.name ASC, c.name ASC
                {limit_clause}""",
            *params,
        )


@router.get("/api/v1/playlist.m3u")
async def get_playlist_m3u(
    group: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
    ott: Optional[bool] = Query(False),
    limit: int = Query(0, ge=0, le=5000),
    request: Request = None,
):
    rows = await _fetch_channels(group, type, ott, limit)
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
            f'group-title="{r["gn"] or "Lainnya"}",{r["name"] or "Unknown"}'
        )
        lines.append(r["url"])

    content = "\n".join(lines) + "\n"
    etag = hashlib.md5(content.encode()).hexdigest()

    if request:
        if_none_match = request.headers.get("if-none-match")
        if if_none_match and if_none_match.strip('"') == etag:
            return Response(status_code=304)

    return Response(
        content=content,
        media_type="audio/x-mpegurl",
        headers={
            "Content-Disposition": "attachment; filename=istv-playlist.m3u",
            "Cache-Control": "public, max-age=600",
            "ETag": f'"{etag}"',
        },
    )


@router.get("/api/v1/playlist.json")
async def get_playlist_json(
    group: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
    ott: Optional[bool] = Query(False),
    limit: int = Query(0, ge=0, le=5000),
):
    rows = await _fetch_channels(group, type, ott, limit)
    data = [
        {
            "tvg_id": r["tvg_id"],
            "name": r["name"],
            "logo": r["logo"],
            "group": r["gn"] or "Lainnya",
            "url": r["url"],
            "type": r["stream_type"],
            "has_drm": r["has_drm"],
            "headers": _parse(r["headers"]),
        }
        for r in rows
    ]
    content = json.dumps(data, indent=2)
    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": "attachment; filename=istv-playlist.json",
            "Cache-Control": "public, max-age=600",
        },
    )


@router.get("/api/v1/playlist.xml")
async def get_playlist_xml(
    group: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
    ott: Optional[bool] = Query(False),
    limit: int = Query(0, ge=0, le=5000),
):
    rows = await _fetch_channels(group, type, ott, limit)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<playlist xmlns="http://xspf.org/ns/0/">',
             '  <trackList>']
    for r in rows:
        headers = _parse(r["headers"])
        lines.append("    <track>")
        lines.append(f"      <title><![CDATA[{r['name'] or 'Unknown'}]]></title>")
        lines.append(f"      <location>{r['url']}</location>")
        lines.append(f"      <image>{r['logo'] or ''}</image>")
        lines.append(f"      <extension application='istv'>")
        lines.append(f"        <tvg-id>{r['tvg_id'] or ''}</tvg-id>")
        lines.append(f"        <group>{r['gn'] or 'Lainnya'}</group>")
        lines.append(f"        <type>{r['stream_type']}</type>")
        lines.append(f"        <has-drm>{str(r['has_drm']).lower()}</has-drm>")
        if headers:
            lines.append(f"        <headers>{json.dumps(headers)}</headers>")
        lines.append("      </extension>")
        lines.append("    </track>")
    lines.append("  </trackList>")
    lines.append("</playlist>")

    content = "\n".join(lines) + "\n"
    return Response(
        content=content,
        media_type="application/xml",
        headers={
            "Content-Disposition": "attachment; filename=istv-playlist.xml",
            "Cache-Control": "public, max-age=600",
        },
    )
