#!/usr/bin/env python3
"""Standalone script to reload ISTV data directly into NeonDB.
Can be run locally or via GitHub Actions (bypasses Vercel 10s timeout)."""

import asyncio
import json
import logging
import os
import sys

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reload")

M3U_URL = os.environ.get(
    "M3U_URL",
    "https://raw.githubusercontent.com/dhasap/dhanytv/main/dhanytv.m3u",
)
EPG_URL = os.environ.get(
    "EPG_URL",
    "https://raw.githubusercontent.com/dhasap/dhanytv/main/epg.xml",
)
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable is required")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.parser.m3u import parse_m3u
from app.parser.epg_xml import parse_epg

TRUNCATE_SQL = """
TRUNCATE TABLE channels, categories, epg_programs RESTART IDENTITY CASCADE;
"""

CREATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    channel_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS channels (
    id SERIAL PRIMARY KEY,
    tvg_id VARCHAR(255) NOT NULL DEFAULT '',
    name VARCHAR(255) NOT NULL DEFAULT '',
    logo TEXT DEFAULT '',
    category_id INTEGER REFERENCES categories(id),
    url TEXT NOT NULL DEFAULT '',
    stream_type VARCHAR(10) NOT NULL DEFAULT 'hls',
    has_drm BOOLEAN NOT NULL DEFAULT FALSE,
    drm_info JSONB DEFAULT NULL,
    headers JSONB DEFAULT '{}',
    kodiprops JSONB DEFAULT '{}',
    country VARCHAR(100) DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_channels_tvg_id ON channels(tvg_id);
CREATE INDEX IF NOT EXISTS idx_channels_category ON channels(category_id);
CREATE INDEX IF NOT EXISTS idx_channels_type ON channels(stream_type);
CREATE INDEX IF NOT EXISTS idx_channels_active ON channels(is_active);
CREATE TABLE IF NOT EXISTS epg_programs (
    id BIGSERIAL PRIMARY KEY,
    channel_tvg_id VARCHAR(255) NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    description TEXT DEFAULT '',
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    category VARCHAR(255) DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_epg_channel ON epg_programs(channel_tvg_id);
CREATE INDEX IF NOT EXISTS idx_epg_start ON epg_programs(start_time);
CREATE INDEX IF NOT EXISTS idx_epg_end ON epg_programs(end_time);
DELETE FROM rate_limits WHERE requested_at < NOW() - INTERVAL '1 hour';
"""

COUNTRY_MAP = {
    "TV JEPANG": "Japan",
    "Japan": "Japan",
    "Korea": "South Korea",
    "Korea Selatan": "South Korea",
    "Korean Channels": "South Korea",
    "United States": "United States",
    "US": "United States",
    "United Kingdom": "United Kingdom",
    "UK": "United Kingdom",
    "Brazil": "Brazil",
    "India": "India",
    "Thailand": "Thailand",
    "Malaysia": "Malaysia",
    "TV Malaysia": "Malaysia",
    "Singapore": "Singapore",
    "Mediacorp Singapore": "Singapore",
    "China": "China",
    "Turkey": "Turkey",
    "Turki": "Turkey",
    "Germany": "Germany",
    "Jerman": "Germany",
    "France": "France",
    "Perancis": "France",
    "Russia": "Russia",
    "Rusia": "Russia",
    "Italy": "Italy",
    "Italia": "Italy",
    "Spain": "Spain",
    "Spanyol": "Spain",
    "Mexico": "Mexico",
    "Meksiko": "Mexico",
    "Philippines": "Philippines",
    "Filipina": "Philippines",
    "Vietnam": "Vietnam",
    "Egypt": "Egypt",
    "Mesir": "Egypt",
    "Saudi Arabia": "Saudi Arabia",
    "Nigeria": "Nigeria",
    "South Africa": "South Africa",
    "Afrika Selatan": "South Africa",
    "Bangladesh": "Bangladesh",
    "Iran": "Iran",
    "Pakistan": "Pakistan",
    "Kenya": "Kenya",
    "Argentina": "Argentina",
    "Colombia": "Colombia",
    "Kolombia": "Colombia",
    "UAE & Arab": "UAE",
    "UAE": "UAE",
}


def detect_country(group_name: str) -> str:
    for key, country in COUNTRY_MAP.items():
        if key.lower() in group_name.lower():
            return country
    return ""


async def reload():
    logger.info("Downloading M3U...")
    async with httpx.AsyncClient(timeout=120.0) as client:
        m3u_resp = await client.get(M3U_URL)
        epg_resp = await client.get(EPG_URL)

    m3u_resp.raise_for_status()
    epg_resp.raise_for_status()
    logger.info(f"M3U: {len(m3u_resp.text)} bytes, EPG: {len(epg_resp.text)} bytes")

    channels = parse_m3u(m3u_resp.text)
    programs = parse_epg(epg_resp.text)
    logger.info(f"Parsed: {len(channels)} channels, {len(programs)} EPG programs")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        async with conn.transaction():
            await conn.execute(CREATE_SCHEMA_SQL)
            await conn.execute(TRUNCATE_SQL)
            logger.info("Schema ensured, tables truncated")

            cat_map = {}
            for ch in channels:
                if ch.group not in cat_map:
                    row = await conn.fetchrow(
                        "INSERT INTO categories (name) VALUES ($1) ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name RETURNING id",
                        ch.group,
                    )
                    cat_map[ch.group] = row["id"]
                    country = detect_country(ch.group)
                    ch.country = country

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
                cnt = await conn.fetchval(
                    "SELECT COUNT(*) FROM channels WHERE category_id = $1", cat_id
                )
                await conn.execute(
                    "UPDATE categories SET channel_count = $1 WHERE id = $2", cnt, cat_id
                )

            batch = []
            for p in programs:
                batch.append(
                    (p.channel_tvg_id, p.title, p.description, p.start_time, p.end_time, p.category)
                )
                if len(batch) >= 500:
                    await conn.executemany(
                        "INSERT INTO epg_programs (channel_tvg_id, title, description, start_time, end_time, category) VALUES ($1,$2,$3,$4,$5,$6)",
                        batch,
                    )
                    batch = []
            if batch:
                await conn.executemany(
                    "INSERT INTO epg_programs (channel_tvg_id, title, description, start_time, end_time, category) VALUES ($1,$2,$3,$4,$5,$6)",
                    batch,
                )

            logger.info(
                f"Done: {len(channels)} channels, {len(programs)} EPG, {len(cat_map)} categories"
            )
    finally:
        await conn.close()


if __name__ == "__main__":
    logger.info("=== ISTV Data Reload ===")
    asyncio.run(reload())
