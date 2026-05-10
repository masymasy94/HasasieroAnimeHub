from pydantic import BaseModel


class SettingsResponse(BaseModel):
    download_dir: str
    host_download_path: str
    max_concurrent_downloads: int
    telegram_bot_token: str
    telegram_chat_id: str
    jellyfin_url: str
    jellyfin_api_key: str
    jellyfin_enabled: bool


class SettingsUpdate(BaseModel):
    download_dir: str | None = None
    max_concurrent_downloads: int | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    jellyfin_url: str | None = None
    jellyfin_api_key: str | None = None
    jellyfin_enabled: bool | None = None
