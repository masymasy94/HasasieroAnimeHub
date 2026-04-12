from pathlib import Path

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..schemas.setting import SettingsResponse, SettingsUpdate
from ..services.notification_service import NotificationService
from ..services.settings_service import SettingsService
from .deps import get_notification_service, get_settings_service

router = APIRouter()


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(svc: SettingsService = Depends(get_settings_service)):
    return await svc.get_settings()


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(
    update: SettingsUpdate,
    svc: SettingsService = Depends(get_settings_service),
):
    return await svc.update_settings(update)


@router.post("/settings/telegram/test")
async def test_telegram(
    notification: NotificationService = Depends(get_notification_service),
):
    """Send a test message to verify Telegram configuration."""
    if not await notification.is_configured():
        return {"success": False, "error": "Bot token e Chat ID sono richiesti"}
    success = await notification.send_telegram("Hasasiero: connessione Telegram OK")
    if success:
        return {"success": True}
    return {"success": False, "error": "Invio fallito — controlla token e chat ID"}


class BrowseEntry(BaseModel):
    name: str
    path: str
    is_dir: bool


class BrowseResponse(BaseModel):
    current: str
    parent: str | None
    entries: list[BrowseEntry]


@router.get("/settings/browse", response_model=BrowseResponse)
async def browse_directories(path: str = Query("/")):
    """Browse filesystem directories for folder picker."""
    target = Path(path).resolve()
    if not target.is_dir():
        target = Path("/")

    parent = str(target.parent) if target != target.parent else None

    entries: list[BrowseEntry] = []
    try:
        for item in sorted(target.iterdir()):
            if item.name.startswith("."):
                continue
            if item.is_dir():
                entries.append(BrowseEntry(name=item.name, path=str(item), is_dir=True))
    except PermissionError:
        pass

    return BrowseResponse(current=str(target), parent=parent, entries=entries)
