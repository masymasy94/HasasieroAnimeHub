"""Dependency injection helpers — extract services from app.state."""

from fastapi import Request

from ..services.download_service import DownloadService
from ..services.notification_service import NotificationService
from ..services.nas_queue import NasIOQueue
from ..services.providers import ProviderRegistry
from ..services.settings_service import SettingsService
from ..services.tracker_service import TrackerService
from ..services.ws_manager import WebSocketManager


def get_provider_registry(request: Request) -> ProviderRegistry:
    return request.app.state.provider_registry


def get_download_service(request: Request) -> DownloadService:
    return request.app.state.download_service


def get_nas_queue(request: Request) -> NasIOQueue:
    return request.app.state.nas_queue


def get_settings_service(request: Request) -> SettingsService:
    return request.app.state.settings_service


def get_ws_manager(request: Request) -> WebSocketManager:
    return request.app.state.ws_manager


def get_tracker_service(request: Request) -> TrackerService:
    return request.app.state.tracker_service


def get_scheduled_download_service(request: Request):
    return request.app.state.scheduled_download_service


def get_db_session_factory(request: Request):
    return request.app.state.db_session_factory


def get_notification_service(request: Request) -> NotificationService:
    return request.app.state.notification_service
