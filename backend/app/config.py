from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Absolute path for Docker; relative fallback for local dev
    database_url: str = "sqlite+aiosqlite:////data/animeunity.db"
    download_dir: str = "/downloads"
    max_concurrent_downloads: int = 2
    animeunity_domain: str = "www.animeunity.so"
    log_level: str = "INFO"
    impersonate_browser: str = "chrome"
    static_dir: str = "static"  # Path to built frontend assets
    host_download_path: str = ""  # Actual path on the host OS (for display)
    # Enrich episode titles from AnimeClick (Italian) before embedding/NFO.
    animeclick_titles_enabled: bool = True
    animeclick_base_url: str = "https://www.animeclick.it"

    @property
    def animeunity_base_url(self) -> str:
        return f"https://{self.animeunity_domain}"

    @property
    def download_path(self) -> Path:
        return Path(self.download_dir)

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}


settings = Settings()
