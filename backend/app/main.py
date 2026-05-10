import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .config import settings
from .database import async_session, init_db
from .services.animeunity_client import AnimeUnityClient
from .services.download_service import DownloadService
from .services.metadata_service import MetadataService
from .services.nas_queue import NasIOQueue
from .services.providers import ProviderRegistry
from .services.providers.animeunity_provider import AnimeUnityProvider
from .services.providers.animeworld_provider import AnimeWorldProvider
from .services.providers.animesaturn_provider import AnimeSaturnProvider
from .services.settings_service import SettingsService
from .services.notification_service import NotificationService
from .services.jellyfin_service import JellyfinService
from .services.scheduled_download_service import ScheduledDownloadService
from .services.tracker_service import TrackerService
from .services.ws_manager import WebSocketManager
from .api.router import api_router

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Resolve static dir
STATIC_DIR = Path(settings.static_dir)
if not STATIC_DIR.is_absolute():
    STATIC_DIR = Path.cwd() / STATIC_DIR
STATIC_EXISTS = STATIC_DIR.is_dir()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Hasasiero AnimeHub...")

    await init_db()
    logger.info("Database initialized")

    download_dir = Path(settings.download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)

    # Create provider registry
    registry = ProviderRegistry()
    registry.register(AnimeUnityProvider())
    registry.register(AnimeWorldProvider())
    registry.register(AnimeSaturnProvider())

    # Create services and store in app.state for dependency injection
    client = AnimeUnityClient()
    ws_manager = WebSocketManager()
    metadata_svc = MetadataService(client)

    # NAS I/O queue — all NAS operations go through here
    nas_queue = NasIOQueue(nas_dir=download_dir)
    nas_queue.start()

    app.state.provider_registry = registry
    app.state.settings_service = SettingsService(async_session)
    app.state.ws_manager = ws_manager
    app.state.nas_queue = nas_queue
    app.state.db_session_factory = async_session

    jellyfin_service = JellyfinService(async_session)
    app.state.jellyfin_service = jellyfin_service

    download_service = DownloadService(
        db_session_factory=async_session,
        provider_registry=registry,
        metadata_service=metadata_svc,
        ws_manager=ws_manager,
        nas_queue=nas_queue,
        download_dir=download_dir,
        max_concurrent=settings.max_concurrent_downloads,
        jellyfin_service=jellyfin_service,
    )
    app.state.download_service = download_service
    download_service.start()

    tracker_service = TrackerService(
        db_session_factory=async_session,
        provider_registry=registry,
        download_service=download_service,
    )
    app.state.tracker_service = tracker_service
    tracker_service.start()

    notification_service = NotificationService(async_session)
    app.state.notification_service = notification_service

    scheduled_download_service = ScheduledDownloadService(
        db_session_factory=async_session,
        provider_registry=registry,
        download_service=download_service,
        notification_service=notification_service,
    )
    app.state.scheduled_download_service = scheduled_download_service
    scheduled_download_service.start()

    logger.info("Ready — UI at http://0.0.0.0:8000")
    yield

    # Cleanup
    await scheduled_download_service.stop()
    await tracker_service.stop()
    await download_service.stop()
    await nas_queue.stop()
    await registry.close_all()
    await client.close()
    logger.info("Stopped")


# ── Create app ──
app = FastAPI(
    title="Hasasiero AnimeHub",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount API routes at module level ──
app.include_router(api_router)


# ── Health check ──
@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ── SPA fallback: serve frontend for non-API routes ──
if STATIC_EXISTS:
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        file_path = STATIC_DIR / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        index = STATIC_DIR / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse({"detail": "Not found"}, status_code=404)
