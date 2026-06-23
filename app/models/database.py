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

CREATE TABLE IF NOT EXISTS rate_limits (
    id BIGSERIAL PRIMARY KEY,
    ip_address VARCHAR(45) NOT NULL,
    endpoint VARCHAR(255) NOT NULL DEFAULT '',
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rate_ip ON rate_limits(ip_address, requested_at);
"""

TRUNCATE_SQL = """
TRUNCATE TABLE channels, categories, epg_programs RESTART IDENTITY CASCADE;
"""
