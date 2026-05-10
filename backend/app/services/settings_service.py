import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..config import settings as app_settings
from ..models.setting import Setting
from ..schemas.setting import SettingsResponse, SettingsUpdate

logger = logging.getLogger(__name__)

DEFAULTS = {
    "download_dir": app_settings.download_dir,
    "max_concurrent_downloads": str(app_settings.max_concurrent_downloads),
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "jellyfin_url": "http://192.168.3.54:8096",
    "jellyfin_api_key": "1053bc875c2744f79754c2586a30de45",
    "jellyfin_enabled": "true",
}


class SettingsService:
    def __init__(self, db_session_factory: async_sessionmaker[AsyncSession]):
        self._db = db_session_factory

    async def get_settings(self) -> SettingsResponse:
        values = dict(DEFAULTS)
        async with self._db() as session:
            result = await session.execute(select(Setting))
            for setting in result.scalars().all():
                values[setting.key] = setting.value

        return SettingsResponse(
            download_dir=values["download_dir"],
            host_download_path=app_settings.host_download_path,
            max_concurrent_downloads=int(values["max_concurrent_downloads"]),
            telegram_bot_token=values.get("telegram_bot_token", ""),
            telegram_chat_id=values.get("telegram_chat_id", ""),
            jellyfin_url=values.get("jellyfin_url", ""),
            jellyfin_api_key=values.get("jellyfin_api_key", ""),
            jellyfin_enabled=values.get("jellyfin_enabled", "false") == "true",
        )

    async def update_settings(self, update: SettingsUpdate) -> SettingsResponse:
        async with self._db() as session:
            if update.download_dir is not None:
                await self._upsert(session, "download_dir", update.download_dir)
            if update.max_concurrent_downloads is not None:
                await self._upsert(
                    session,
                    "max_concurrent_downloads",
                    str(update.max_concurrent_downloads),
                )
            if update.telegram_bot_token is not None:
                await self._upsert(session, "telegram_bot_token", update.telegram_bot_token)
            if update.telegram_chat_id is not None:
                await self._upsert(session, "telegram_chat_id", update.telegram_chat_id)
            if update.jellyfin_url is not None:
                await self._upsert(session, "jellyfin_url", update.jellyfin_url.rstrip("/"))
            if update.jellyfin_api_key is not None:
                await self._upsert(session, "jellyfin_api_key", update.jellyfin_api_key)
            if update.jellyfin_enabled is not None:
                await self._upsert(
                    session, "jellyfin_enabled", "true" if update.jellyfin_enabled else "false"
                )
            await session.commit()

        return await self.get_settings()

    async def _upsert(self, session: AsyncSession, key: str, value: str) -> None:
        existing = await session.get(Setting, key)
        if existing:
            existing.value = value
        else:
            session.add(Setting(key=key, value=value))
