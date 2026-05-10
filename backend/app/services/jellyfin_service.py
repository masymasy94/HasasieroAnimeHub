"""Jellyfin webhook — triggers a library refresh after a download lands on the NAS.

Uses the official ``POST {server}/Library/Refresh`` endpoint (the same one Sonarr/Radarr
Connect notifications hit) authenticated via the ``X-Emby-Token`` header. A single
refresh call kicks Jellyfin's scheduled "Scan Media Library" task; Jellyfin itself
de-duplicates concurrent scans and only re-fetches metadata for changed items.

Multiple completions in a short window are coalesced into a single refresh via a
debounce timer so a binge of N episodes only triggers one scan.
"""
from __future__ import annotations

import asyncio
import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..models.setting import Setting
from .settings_service import DEFAULTS

logger = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 5.0
REQUEST_TIMEOUT = 15.0


class JellyfinService:
    def __init__(self, db_session_factory: async_sessionmaker[AsyncSession]):
        self._db = db_session_factory
        self._debounce_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    # ── Configuration ──

    async def _get_config(self) -> tuple[str, str, bool]:
        """Return (base_url, api_key, enabled). Falls back to DEFAULTS when
        the corresponding Settings row is missing — keeps behaviour consistent
        with SettingsService.get_settings()."""
        async with self._db() as session:
            url_setting = await session.get(Setting, "jellyfin_url")
            key_setting = await session.get(Setting, "jellyfin_api_key")
            enabled_setting = await session.get(Setting, "jellyfin_enabled")

        url = (url_setting.value if url_setting else DEFAULTS["jellyfin_url"]).rstrip("/")
        key = key_setting.value if key_setting else DEFAULTS["jellyfin_api_key"]
        enabled_str = enabled_setting.value if enabled_setting else DEFAULTS["jellyfin_enabled"]
        return url, key, enabled_str == "true"

    async def is_configured(self) -> bool:
        url, key, _ = await self._get_config()
        return bool(url and key)

    async def is_enabled(self) -> bool:
        url, key, enabled = await self._get_config()
        return bool(url and key and enabled)

    # ── Public API ──

    async def trigger_refresh(self) -> None:
        """Schedule a debounced library refresh.

        Safe to call from the NAS-move success callback — multiple calls within
        DEBOUNCE_SECONDS coalesce into one HTTP request to Jellyfin.
        """
        if not await self.is_enabled():
            return

        async with self._lock:
            if self._debounce_task and not self._debounce_task.done():
                self._debounce_task.cancel()
            self._debounce_task = asyncio.create_task(self._debounced_refresh())

    async def test_connection(self) -> tuple[bool, str | None]:
        """Verify URL + key by calling /System/Info. Returns (ok, error_message)."""
        url, key, _ = await self._get_config()
        if not url or not key:
            return False, "URL e API key sono richiesti"

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(
                    f"{url}/System/Info",
                    headers={"X-Emby-Token": key},
                )
                if response.status_code == 401:
                    return False, "API key non valida"
                response.raise_for_status()
                data = response.json()
                server_name = data.get("ServerName", "Jellyfin")
                version = data.get("Version", "?")
                return True, f"Connesso a {server_name} (v{version})"
        except httpx.HTTPStatusError as exc:
            return False, f"HTTP {exc.response.status_code}"
        except Exception as exc:
            return False, f"Connessione fallita: {exc}"

    # ── Internals ──

    async def _debounced_refresh(self) -> None:
        try:
            await asyncio.sleep(DEBOUNCE_SECONDS)
        except asyncio.CancelledError:
            return
        await self._send_refresh()

    async def _send_refresh(self) -> None:
        url, key, enabled = await self._get_config()
        if not (url and key and enabled):
            return

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{url}/Library/Refresh",
                    headers={"X-Emby-Token": key},
                )
                response.raise_for_status()
            logger.info("Jellyfin library refresh triggered")
        except Exception as exc:
            logger.warning("Failed to trigger Jellyfin refresh: %s", exc)
