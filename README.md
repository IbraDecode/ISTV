<div align="center">
  <img src="https://avatars.githubusercontent.com/u/244273660?v=4&size=128" width="128" height="128" style="border-radius:50%" alt="Ibra Decode"/>
  <h1>ISTV API</h1>
  <p><strong>Free IPTV Channel API</strong> — 1.045+ channel TV live dari Indonesia & 27+ negara</p>
  <p>
    <a href="https://istv-azure.vercel.app/api/v1/docs">Swagger Docs</a> ·
    <a href="https://istv-azure.vercel.app/api/v1/stats">Stats</a> ·
    <a href="https://istv-azure.vercel.app/api/v1/playlist.m3u">Playlist M3U</a>
  </p>
  <p>
    <img src="https://img.shields.io/badge/python-3.12-blue" alt="Python"/>
    <img src="https://img.shields.io/badge/FastAPI-0.115-green" alt="FastAPI"/>
    <img src="https://img.shields.io/badge/PostgreSQL-NeonDB-purple" alt="NeonDB"/>
    <img src="https://img.shields.io/badge/deploy-Vercel-black" alt="Vercel"/>
  </p>
</div>

---

Dibuat oleh [Ibra Decode](https://github.com/IbraDecode) dengan fokus pada keamanan, performa, dan kemudahan penggunaan.

## Base URL

```
https://istv-azure.vercel.app
```

Dokumentasi interaktif: [https://istv-azure.vercel.app/api/v1/docs](https://istv-azure.vercel.app/api/v1/docs)

---

## Quick Start

```bash
# Semua channel
curl "https://istv-azure.vercel.app/api/v1/channels?page=1&limit=5"

# Cari channel
curl "https://istv-azure.vercel.app/api/v1/search?q=TVRI"

# Acara sedang tayang
curl "https://istv-azure.vercel.app/api/v1/epg/now"

# Download playlist
curl -o playlist.m3u "https://istv-azure.vercel.app/api/v1/playlist.m3u"
curl -o playlist-ott.m3u "https://istv-azure.vercel.app/api/v1/playlist.m3u?ott=true"

# Playlist JSON
curl -o playlist.json "https://istv-azure.vercel.app/api/v1/playlist.json"

# Statistik
curl "https://istv-azure.vercel.app/api/v1/stats"

# Cari program EPG
curl "https://istv-azure.vercel.app/api/v1/epg/search?q=Bola"

# Daftar negara
curl "https://istv-azure.vercel.app/api/v1/countries"
```

---

## Endpoints Lengkap

### Channels

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/channels` | Semua channel (pagination + filter) |
| GET | `/api/v1/channels/{tvg_id}` | Detail channel + EPG now/next |
| GET | `/api/v1/channels/{tvg_id}/stream` | Info stream URL + headers |

**Filter `/channels`:**

| Parameter | Type | Deskripsi |
|-----------|------|-----------|
| `group` | string | Filter grup (contoh: "Sports") |
| `type` | string | Tipe stream: `hls`, `dash` |
| `has_drm` | bool | Filter channel ber-DRM |
| `country` | string | Filter negara |
| `search` | string | Cari nama channel |
| `page` | int | Halaman (default: 1) |
| `limit` | int | Maks 100 per halaman |

### Categories

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/categories` | Semua kategori + jumlah channel |
| GET | `/api/v1/categories/{name}/channels` | Channel dalam kategori |

### Countries

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/countries` | Semua negara + jumlah channel |
| GET | `/api/v1/countries/{name}/channels` | Channel per negara |

### EPG (Electronic Program Guide)

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/epg` | Semua jadwal (filter: `channel`, `date`) |
| GET | `/api/v1/epg/now` | Acara sedang tayang di semua channel |
| GET | `/api/v1/epg/now/{tvg_id}` | Acara sekarang di channel tertentu |
| GET | `/api/v1/epg/{tvg_id}` | Jadwal channel tertentu |
| GET | `/api/v1/epg/search?q=` | Cari program EPG |

### Playlist

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/playlist.m3u` | Download playlist M3U (format IPTV player) |
| GET | `/api/v1/playlist.json` | Download playlist JSON |
| GET | `/api/v1/playlist.xml` | Download playlist XML (XSPF) |

**Filter playlist:** `?group=`, `?type=hls`, `?ott=true` (no DRM), `?limit=N`

### Search & Stats

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/search?q=` | Cari channel (ranked by relevance) |
| GET | `/api/v1/stats` | Statistik lengkap |

### System

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/health` | Health check |
| POST | `/api/v1/admin/reload` | Reload data dari source |
| GET | `/api/v1/docs` | Swagger UI |
| GET | `/api/v1/redoc` | ReDoc UI |

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
| **Error Handling** | No stack trace di production |
| **CORS** | Terkontrol via environment |
| **HTTPS Only** | HSTS preload |

---

## Stack

| Layer | Teknologi |
|-------|-----------|
| **Bahasa** | Python 3.12 |
| **Framework** | FastAPI |
| **Database** | PostgreSQL (NeonDB) |
| **Cache** | In-memory (TTL) |
| **Parser** | Custom M3U & XMLTV parser |
| **Deploy** | Vercel (serverless) / Docker |
| **Auto-Reload** | GitHub Actions (daily) |

---

## Lisensi

MIT License &copy; 2026 [Ibra Decode](https://github.com/IbraDecode) — bebas digunakan, dimodifikasi, dan didistribusikan.
