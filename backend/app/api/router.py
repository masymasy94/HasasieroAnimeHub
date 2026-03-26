from fastapi import APIRouter

from .search import router as search_router
from .anime import router as anime_router
from .downloads import router as downloads_router
from .settings import router as settings_router
from .sites import router as sites_router
from .tracked import router as tracked_router
from .stream import router as stream_router
from .ws import router as ws_router

api_router = APIRouter(prefix="/api")
api_router.include_router(search_router, tags=["search"])
api_router.include_router(anime_router, tags=["anime"])
api_router.include_router(downloads_router, tags=["downloads"])
api_router.include_router(settings_router, tags=["settings"])
api_router.include_router(sites_router, tags=["sites"])
api_router.include_router(tracked_router, tags=["tracked"])
api_router.include_router(stream_router, tags=["stream"])
api_router.include_router(ws_router, tags=["websocket"])
