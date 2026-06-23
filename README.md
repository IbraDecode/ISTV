# ISTV API

**Free IPTV Channel API** — Daftar channel TV live dari Indonesia & 27+ negara, disajikan lewat REST API yang cepat, aman, dan gratis.

## Fitur

- **1.046+ channel** live TV dari 27+ negara
- **EPG lengkap** — jadwal acara now/next
- **REST API** — JSON terstruktur dengan pagination
- **Playlist M3U** — download langsung untuk player IPTV (VLC, Kodi, TiviMate, dll)
- **Pencarian real-time** — cari channel berdasarkan nama
- **Filter lengkap** — group, tipe stream (hls/dash), DRM, negara
- **Keamanan tingkat atas** — rate limiting, security headers, input validation, parameterized queries
- **Dokumentasi Swagger** — interactive API docs

## Base URL

```
https://istv-api.my.id/api/v1
```

## Quick Start

### Cari semua channel

```bash
curl https://istv-api.my.id/api/v1/channels?page=1&limit=5
```

### Cari channel tertentu

```bash
curl https://istv-api.my.id/api/v1/search?q=TVRI
```

### Lihat acara yang sedang tayang

```bash
curl https://istv-api.my.id/api/v1/epg/now
```

### Download playlist M3U

```bash
curl -o playlist.m3u https://istv-api.my.id/api/v1/playlist.m3u
curl -o playlist-ott.m3u https://istv-api.my.id/api/v1/playlist.m3u?ott=true
```

### Statistik

```bash
curl https://istv-api.my.id/api/v1/stats
```

---

## Endpoints

### Channels

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/channels` | Semua channel (dengan pagination & filter) |
| GET | `/api/v1/channels/{tvg_id}` | Detail channel |
| GET | `/api/v1/channels/{tvg_id}/stream` | Info stream URL + headers |

**Parameters `/channels`:**

| Parameter | Type | Default | Deskripsi |
|-----------|------|---------|-----------|
| `group` | string | - | Filter grup/kategori |
| `type` | string | - | Tipe stream: `hls`, `dash` |
| `has_drm` | bool | - | Filter channel ber-DRM |
| `country` | string | - | Filter negara |
| `search` | string | - | Cari berdasarkan nama |
| `page` | int | 1 | Halaman |
| `limit` | int | 50 | Maks 100 |

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "tvg_id": "TVRI.id",
      "name": "TVRI",
      "logo": "https://...",
      "group_name": "WorldCup 2026",
      "url": "https://...",
      "stream_type": "hls",
      "has_drm": false,
      "drm_info": null,
      "headers": {"Referer": "https://tvri.go.id/"},
      "country": "",
      "is_active": true
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 1046,
    "total_pages": 21
  }
}
```

### Categories

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/categories` | Semua kategori + jumlah channel |
| GET | `/api/v1/categories/{name}/channels` | Channel dalam kategori tertentu |

### EPG (Electronic Program Guide)

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/epg` | Semua jadwal (filter: `channel`, `date`) |
| GET | `/api/v1/epg/now` | Semua channel + acara sedang tayang |
| GET | `/api/v1/epg/now/{tvg_id}` | Acara sedang tayang di channel tertentu |
| GET | `/api/v1/epg/{tvg_id}` | Jadwal channel tertentu |

### Playlist

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/playlist.m3u` | Download playlist M3U |

**Parameters:**

| Parameter | Type | Default | Deskripsi |
|-----------|------|---------|-----------|
| `group` | string | - | Filter grup |
| `type` | string | - | Tipe stream: `hls`, `dash` |
| `ott` | bool | false | Mode OTT: exclude DRM |

### Search

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/search?q=` | Cari channel |

### Stats

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/stats` | Statistik lengkap |

### System

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/health` | Health check |
| POST | `/api/v1/admin/reload` | Reload data dari source |

---

## Keamanan

ISTV API menerapkan lapisan keamanan:

- **Rate Limiting**: 100 request per 60 detik per IP
- **Blokir IP Private**: Request dari IP lokal/private ditolak
- **Security Headers**: X-Content-Type-Options, X-Frame-Options, HSTS, CSP, dll
- **SQL Injection Prevention**: Semua query menggunakan parameterized queries
- **Input Validation**: Validasi ketat semua input via Pydantic
- **No Info Leak**: Error production tidak menampilkan stack trace
- **CORS Terkontrol**: Bisa di-restrict per origin
- **HTTPS Only**: HSTS preload, Redirect HTTP→HTTPS

---

## Stack

- **Bahasa**: Python 3.12
- **Framework**: FastAPI
- **Database**: PostgreSQL (NeonDB)
- **Parser**: Custom M3U & XML parser
- **Deploy**: Docker

## Lisensi

MIT License — bebas digunakan, dimodifikasi, dan didistribusikan.
