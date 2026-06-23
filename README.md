<div align="center">
  <img src="https://avatars.githubusercontent.com/u/244273660?v=4&size=256" width="128" height="128" style="border-radius:50%" alt="IbraDecode"/>
  <h1>ISTV API</h1>
  <p><strong>Free IPTV Channel API</strong> — 1.045+ channel TV live dari Indonesia & 27+ negara</p>
  <p>
    <a href="https://tv-api.isplay.my.id/api/v1/docs">Swagger Docs</a> ·
    <a href="https://tv-api.isplay.my.id/api/v1/stats">Stats</a> ·
    <a href="https://tv-api.isplay.my.id/api/v1/channels.csv">CSV</a>
  </p>
  <p>
    <img src="https://img.shields.io/badge/python-3.12-blue" alt="Python"/>
    <img src="https://img.shields.io/badge/FastAPI-0.115-green" alt="FastAPI"/>
    <img src="https://img.shields.io/badge/version-3.0.0-orange" alt="v3"/>
    <img src="https://img.shields.io/badge/PostgreSQL-NeonDB-purple" alt="NeonDB"/>
    <img src="https://img.shields.io/badge/deploy-Vercel-black" alt="Vercel"/>
  </p>
</div>

---

Dibuat oleh [IbraDecode](https://github.com/IbraDecode) dengan organisasi tim **Decode Labs**.

## Base URL

```
https://tv-api.isplay.my.id
```

Dokumentasi interaktif: [https://tv-api.isplay.my.id/api/v1/docs](https://tv-api.isplay.my.id/api/v1/docs)

---

## Quick Start

```bash
# Semua channel
curl "https://tv-api.isplay.my.id/api/v1/channels?page=1&limit=5"

# Cari channel
curl "https://tv-api.isplay.my.id/api/v1/search?q=TVRI"

# Cari channel + EPG sekaligus
curl "https://tv-api.isplay.my.id/api/v1/search/all?q=World"

# Acara sedang tayang
curl "https://tv-api.isplay.my.id/api/v1/epg/now"

# Acara sekarang + berikutnya
curl "https://tv-api.isplay.my.id/api/v1/epg/now?upcoming=true"

# Acara yang akan datang (N jam ke depan)
curl "https://tv-api.isplay.my.id/api/v1/epg/upcoming?hours=6"

# Cari program EPG (multi-field: title, description, all)
curl "https://tv-api.isplay.my.id/api/v1/epg/search?q=Bola&fields=all"

# Channel acak
curl "https://tv-api.isplay.my.id/api/v1/channels/random?limit=5"

# Channel serupa
curl "https://tv-api.isplay.my.id/api/v1/channels/TVRI.id/similar"

# Cek ketersediaan stream
curl "https://tv-api.isplay.my.id/api/v1/channels/TVRI.id/check"

# Export CSV
curl -o channels.csv "https://tv-api.isplay.my.id/api/v1/channels.csv"

# Proxy stream (bypass CORS/geo)
curl -o stream.bin "https://tv-api.isplay.my.id/api/v1/proxy?url=https://example.com/file.ts"

# Download playlist
curl -o playlist.m3u "https://tv-api.isplay.my.id/api/v1/playlist.m3u"
curl -o playlist-ott.m3u "https://tv-api.isplay.my.id/api/v1/playlist.m3u?ott=true"

# Statistik + cache metrics
curl "https://tv-api.isplay.my.id/api/v1/stats"

# Cek kesehatan massal (butuh API key)
curl -X POST "https://tv-api.isplay.my.id/api/v1/admin/health-check?limit=5" -H "x-api-key: bacotbacot"

# Daftar negara
curl "https://tv-api.isplay.my.id/api/v1/countries"
```

---

## Endpoints Lengkap

### Channels

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/channels` | Semua channel (pagination + filter) |
| GET | `/api/v1/channels/{tvg_id}` | Detail channel + EPG now/next |
| GET | `/api/v1/channels/{tvg_id}/stream` | Info stream URL + headers |
| GET | `/api/v1/channels/{tvg_id}/check` | Cek ketersediaan stream (HEAD request) |
| GET | `/api/v1/channels/{tvg_id}/similar` | Channel serupa (kategori sama) |
| GET | `/api/v1/channels/random` | Channel acak (include `epg_now`, cache 1 jam) |

**Filter `/channels` & `/channels/random`:**

| Parameter | Type | Deskripsi |
|-----------|------|-----------|
| `group` | string | Filter grup (contoh: "Sports") |
| `type` | string | Tipe stream: `hls`, `dash` |
| `has_drm` | bool | Filter channel ber-DRM |
| `country` | string | Filter negara |
| `search` | string | Cari nama channel |
| `page` | int | Halaman (default: 1) |
| `limit` | int | Maks 100 per halaman |

**Response `/channels/{tvg_id}/check`:**

```json
{
  "success": true,
  "data": {
    "tvg_id": "TVRI.id",
    "url": "https://...",
    "stream_type": "hls",
    "has_drm": false,
    "reachable": true,
    "status_code": 200,
    "response_time_ms": 361.4,
    "error": null
  }
}
```

### Categories & Countries

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/categories` | Semua kategori + jumlah channel |
| GET | `/api/v1/categories/{name}/channels` | Channel dalam kategori |
| GET | `/api/v1/countries` | Semua negara + jumlah channel |
| GET | `/api/v1/countries/{name}/channels` | Channel per negara |

### EPG (Electronic Program Guide)

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/epg` | Semua jadwal (filter: `channel`, `date`, `filter_placeholder`) |
| GET | `/api/v1/epg/now` | Acara sedang tayang (placeholder otomatis difilter) |
| GET | `/api/v1/epg/now?upcoming=true` | Acara sekarang + berikutnya |
| GET | `/api/v1/epg/now/{tvg_id}` | Acara sekarang di channel tertentu |
| GET | `/api/v1/epg/now/{tvg_id}?upcoming=true` | Acara sekarang + berikutnya di channel tertentu |
| GET | `/api/v1/epg/{tvg_id}` | Jadwal channel tertentu |
| GET | `/api/v1/epg/search` | Cari program EPG (pagination + multi-field) |
| GET | `/api/v1/epg/upcoming` | Program yang akan tayang (parameter `hours`) |
| GET | `/api/v1/epg/program/{id}` | Detail program EPG (termasuk channel info)

**Parameter EPG Search:**

| Parameter | Type | Default | Deskripsi |
|-----------|------|---------|-----------|
| `q` | string | — | Query pencarian (wajib) |
| `fields` | string | `title` | Field dicari: `title`, `description`, `all` |
| `channel` | string | — | Filter channel tvg_id |
| `date` | string | — | Filter tanggal (YYYY-MM-DD) |
| `page` | int | 1 | Halaman |
| `limit` | int | 20 | Maks 100 |

**Parameter EPG Upcoming:**

| Parameter | Type | Default | Deskripsi |
|-----------|------|---------|-----------|
| `hours` | int | 6 | Jeda waktu ke depan (1-72) |
| `channel` | string | — | Filter channel |

### Search

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/search?q=` | Cari channel (ranked by relevance) |
| GET | `/api/v1/search/all?q=` | Cari channel + EPG program sekaligus |

### Playlist

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/playlist.m3u` | Download playlist M3U (format IPTV player) |
| GET | `/api/v1/playlist.json` | Download playlist JSON |
| GET | `/api/v1/playlist.xml` | Download playlist XML (XSPF) |

**Filter playlist:** `?group=`, `?type=hls`, `?ott=true` (no DRM), `?limit=N`

### Tools & Export

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/channels.csv` | Export semua channel ke CSV |
| GET | `/api/v1/proxy?url=` | Proxy stream (bypass CORS/geo restriction) |
| WebSocket | `/api/v1/ws/now` | Live update acara sedang tayang (setiap 30 detik) |

### Stats & System

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/stats` | Statistik lengkap + cache metrics (hit/miss ratio) |
| GET | `/health` | Health check |
| GET | `/api/v1/docs` | Swagger UI |
| GET | `/api/v1/redoc` | ReDoc UI |

### Admin (butuh API key: `X-API-Key: bacotbacot`)

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| POST | `/api/v1/admin/reload` | Reload data dari source M3U & EPG |
| POST | `/api/v1/admin/cleanup-epg` | Hapus placeholder "Jadwal belum tersedia" + duplikat |
| POST | `/api/v1/admin/flush-cache` | Hapus semua cache in-memory |
| GET | `/api/v1/admin/health-check` | Cek ketersediaan stream massal (random N channel) |

---

## Response Format

Semua endpoint mengembalikan format JSON:

```json
{
  "success": true,
  "data": [ ... ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 1045,
    "total_pages": 21
  }
}
```

Error response:

```json
{
  "success": false,
  "error": "Channel not found",
  "code": 404
}
```

---

## Data

| Metrik | Jumlah |
|--------|:------:|
| **Total channel** | **1.045** |
| **Program EPG** | **22.607** |
| **Kategori** | **62** |
| **Negara** | **29** |
| **HLS** | 680 |
| **DASH** | 346 |
| **Dengan DRM** | 239 |

### Negara Tercakup

Japan (48), Malaysia (43), United States (41), South Korea (25), India (22), United Kingdom (20), Turkey (19), Brazil (20), Germany (15), Thailand (15), France (12), Russia (14), China (13), UAE (14), Italy (10), Mexico (14), Egypt (10), Philippines (10), Spain (9), Vietnam (9), Nigeria (9), Saudi Arabia (8), South Africa (8), Argentina (9), Colombia (7), Bangladesh (8), Iran (7), Pakistan (3), Kenya (1), + Indonesia (semua channel lokal)

---

## Keamanan

ISTV API menerapkan lapisan keamanan berlapis:

| Lapisan | Detail |
|---------|--------|
| **Rate Limiting** | 100 request / 60 detik per IP (header `X-RateLimit-Remaining`) |
| **Blokir IP Private** | Request dari IP lokal/private ditolak (403) |
| **Security Headers** | HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy |
| **SQL Injection** | 100% parameterized queries (`$1`, `$2`, ...) |
| **Input Validation** | Pydantic validasi tipe, length, regex |
| **Error Handling** | No stack trace di production, consistent error codes |
| **API Key** | Admin endpoints dilindungi `X-API-Key` header |
| **GZip** | Kompresi response otomatis untuk ukuran >1KB |
| **CORS** | Terkontrol via environment |
| **HTTPS Only** | HSTS preload |

---

## Stack

| Layer | Teknologi |
|-------|-----------|
| **Bahasa** | Python 3.12 |
| **Framework** | FastAPI |
| **Database** | PostgreSQL (NeonDB) |
| **Cache** | In-memory LRU (max 500 entries, hit/miss metrics via `/stats`) |
| **Parser** | Custom M3U & XMLTV parser |
| **Proxy** | Stream proxy via httpx (bypass CORS/geo) |
| **WebSocket** | Live EPG push (30s interval) |
| **Deploy** | Vercel (serverless) / Docker |
| **CI/CD** | GitHub Actions (auto-reload data setiap hari + manual trigger) |

---

## Konfigurasi Environment

| Variable | Default | Deskripsi |
|----------|---------|-----------|
| `DATABASE_URL` | — | PostgreSQL connection string (NeonDB) |
| `M3U_URL` | — | URL source M3U playlist |
| `EPG_URL` | — | URL source XMLTV EPG |
| `ADMIN_API_KEY` | `bacotbacot` | API key untuk admin endpoints |
| `API_RATE_LIMIT` | `100` | Max request per window per IP |
| `API_RATE_WINDOW` | `60` | Window rate limit (detik) |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |
| `ENVIRONMENT` | `production` | `production` / `development` |

---

## Lisensi

MIT License &copy; 2026 [IbraDecode](https://github.com/IbraDecode) — bebas digunakan, dimodifikasi, dan didistribusikan.
