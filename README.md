<p align="center">
  <img src="frontend/public/favicon.svg" width="80" alt="Hasasiero AnimeHub logo" />
</p>

<h1 align="center">Hasasiero AnimeHub</h1>

<p align="center">
  <strong>Self-hosted anime hub — search, stream and download from multiple Italian anime sites.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12" />
  <img src="https://img.shields.io/badge/fastapi-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/react-19-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React 19" />
  <img src="https://img.shields.io/badge/docker-ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License" />
</p>

---

## Features

### Multi-Site Search
Search across **AnimeUnity**, **AnimeWorld** and **AnimeSaturn** simultaneously. Results are unified with source badges, and filterable by site, type (TV/Movie/OVA/Special) and language (SUB/ITA).

### In-Browser Streaming
Watch anime directly in the browser without downloading. The built-in HLS proxy rewrites M3U8 manifests and proxies video segments, handling Referer/CORS restrictions transparently. Supports both MP4 and HLS streams via hls.js.

### Batch Download
Download single episodes, custom ranges, or entire series. Files are organized as `Anime Title/EP001.mp4` with automatic metadata embedding (cover art, title, episode number, genres, plot, year) via ffmpeg.

### Series Tracking
Follow ongoing series and automatically get notified of new episodes. Tracked anime are checked periodically for new releases.

### Fire TV Companion App
Native Android TV app (`firetv/`) built with Jetpack Compose and Media3/ExoPlayer. Browse tracked series, resume playback with Continue Watching, and stream episodes on the big screen with a Plex-style player overlay optimized for D-pad navigation.

### More
- **Real-time progress** via WebSocket (speed, ETA, status)
- **Queue management** with configurable concurrency (1-5 parallel downloads)
- **Resume support** for interrupted downloads (Range headers)
- **Cloudflare bypass** via TLS fingerprint impersonation (curl-cffi)
- **Plex webhook** support for library refresh on download completion
- **Disk monitoring** with low-space warnings
- **Dark UI** inspired by AniList

---

## Supported Sites

| Site | Search | Stream | Download |
|------|--------|--------|----------|
| [AnimeUnity](https://www.animeunity.so) | Yes | Yes | Yes |
| [AnimeWorld](https://www.animeworld.ac) | Yes | Yes | Yes |
| [AnimeSaturn](https://www.animesaturn.cx) | Yes | Yes | Yes |

The provider architecture is modular — adding new sites requires implementing a single `SiteProvider` interface.

---

## Quick Start

**Docker Compose** (recommended):

```yaml
# docker-compose.yml
services:
  animehub:
    image: ghcr.io/masymasy94/hasasieroanamehub:latest
    container_name: animehub
    ports:
      - "8010:8000"
    volumes:
      - animehub-data:/data
      - ~/Downloads/Anime:/downloads
    environment:
      - MAX_CONCURRENT_DOWNLOADS=2
    restart: unless-stopped

volumes:
  animehub-data:
```

```bash
docker compose up -d
```

Open **http://localhost:8010** and start searching.

---

**Docker CLI**:

```bash
docker run -d \
  --name animehub \
  -p 8010:8000 \
  -v animehub-data:/data \
  -v ~/Downloads/Anime:/downloads \
  -e MAX_CONCURRENT_DOWNLOADS=2 \
  --restart unless-stopped \
  ghcr.io/masymasy94/hasasieroanamehub:latest
```

---

**Build from source**:

```bash
git clone https://github.com/masymasy94/HasasieroAnimeHub.git
cd HasasieroAnimeHub
docker compose up -d --build
```

---

## Configuration

| Variable | Description | Default |
|---|---|---|
| `DOWNLOAD_PATH` | Host path for downloaded files | `~/Downloads/Anime` |
| `MAX_CONCURRENT_DOWNLOADS` | Parallel downloads (1-5) | `2` |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `PORT` | Host port for the web UI | `8010` |

### Volumes

| Container Path | Purpose |
|---|---|
| `/data` | SQLite database (persistent) |
| `/downloads` | Downloaded anime files |

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), curl-cffi, BeautifulSoup4, httpx |
| **Frontend** | React 19, TypeScript, Vite 8, Tailwind CSS 4, TanStack Query 5, hls.js |
| **Fire TV App** | Kotlin, Jetpack Compose, Media3 ExoPlayer, Hilt, Navigation Compose |
| **Infrastructure** | Docker (multi-stage build), SQLite (WAL), ffmpeg |

---

## Architecture

```
┌───────────────────────────────────────────────────────────┐
│                       Browser                             │
│   React 19 + hls.js + TanStack Query + Tailwind CSS       │
└────────────┬──────────────────────┬───────────────────────┘
             │ REST API             │ WebSocket
             ▼                      ▼
┌──────────────────────────────────────────────────────────┐
│                    FastAPI (Uvicorn)                     │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │              Provider Registry                     │  │
│  │  ┌──────────┐ ┌──────────┐ ┌───────────────┐       │  │
│  │  │AnimeUnity│ │AnimeWorld│ │ AnimeSaturn   │       │  │
│  │  └──────────┘ └──────────┘ └───────────────┘       │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│  │ Search   │ │ Download │ │ Stream   │ │ Tracker  │     │
│  │ Service  │ │ Service  │ │ Proxy    │ │ Service  │     │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘     │
│                                                          │
│  ┌──────────────────────┐  ┌───────────────────────┐     │
│  │  Metadata Service    │  │   SQLite (aiosqlite)  │     │
│  │  (ffmpeg embed)      │  │   via SQLAlchemy ORM  │     │
│  └──────────────────────┘  └───────────────────────┘     │
└──────────────────────────────────────────────────────────┘
```

---

## API Reference

### Search & Discovery
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/search?title=...` | Multi-site search |
| `GET` | `/api/latest` | Currently airing anime |
| `GET` | `/api/sites` | List available sites |

### Anime
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/anime/{id}-{slug}?site=...` | Anime details |
| `GET` | `/api/anime/{id}-{slug}/episodes?site=...&start=1&end=24` | Episodes (paginated) |

### Streaming
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/stream/source/{episode_id}?site=...` | Resolve stream URL |
| `GET` | `/api/proxy/m3u8?url=...&headers=...` | HLS manifest proxy |
| `GET` | `/api/proxy/segment?url=...&headers=...` | Video segment proxy |

### Downloads
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/downloads` | Enqueue episodes |
| `GET` | `/api/downloads?status=...` | List downloads |
| `DELETE` | `/api/downloads/{id}` | Cancel download |
| `POST` | `/api/downloads/{id}/retry` | Retry failed |
| `GET` | `/api/downloads/{id}/file` | Get completed file |
| `POST` | `/api/downloads/cancel-all` | Cancel all |
| `POST` | `/api/downloads/clear-completed` | Clear completed |

### Tracked Series
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/tracked` | List tracked anime |
| `POST` | `/api/tracked` | Track a series |
| `DELETE` | `/api/tracked/{id}` | Untrack a series |

### Settings & Health
| Method | Endpoint | Description |
|---|---|---|
| `GET/PUT` | `/api/settings` | Get/update settings |
| `GET` | `/api/health` | Health check |
| `ws` | `/api/ws/downloads` | Real-time progress (WebSocket) |

---

## Development

### Prerequisites
- Python 3.12+
- Node.js 20+
- ffmpeg

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## Disclaimer

This project is for **personal use only**. It is not affiliated with, endorsed by, or connected to any of the supported anime sites. The authors do not host or distribute any copyrighted content. Users are responsible for ensuring compliance with applicable laws in their jurisdiction.
