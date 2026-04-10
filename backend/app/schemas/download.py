from datetime import datetime

from pydantic import BaseModel


class EpisodeDownloadRequest(BaseModel):
    episode_id: int
    episode_number: str
    episode_title: str | None = None


class DownloadRequest(BaseModel):
    anime_id: int
    anime_title: str
    anime_slug: str
    cover_url: str | None = None
    genres: list[str] = []
    plot: str | None = None
    year: str | None = None
    source_site: str = "animeunity"
    episodes: list[EpisodeDownloadRequest]
    # Optional overrides used by scheduled downloads
    dest_folder_override: str | None = None
    filename_template: str | None = None
    filename_template_type: str | None = None
    scheduled_download_id: int | None = None


class DownloadStatus(BaseModel):
    id: int
    anime_id: int
    anime_title: str
    anime_slug: str
    episode_id: int
    episode_number: str
    episode_title: str | None = None
    source_site: str = "animeunity"
    status: str
    progress: float
    downloaded_bytes: int
    total_bytes: int
    speed_bps: int
    file_path: str | None
    host_file_path: str | None = None
    file_exists: bool = False
    retry_count: int = 0
    max_retries: int = 5
    error_message: str | None
    retry_count: int = 0
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class DownloadsResponse(BaseModel):
    downloads: list[DownloadStatus]
