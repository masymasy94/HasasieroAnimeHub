from datetime import datetime

from pydantic import BaseModel, Field


class ScheduleCreate(BaseModel):
    anime_id: int
    anime_slug: str
    anime_title: str
    cover_url: str | None = None
    source_site: str
    dest_folder: str = Field(..., description="Relative to /downloads")
    filename_template: str
    filename_template_type: str  # "preset" | "custom"
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    dest_folder: str | None = None
    filename_template: str | None = None
    filename_template_type: str | None = None
    enabled: bool | None = None


class ActiveDownload(BaseModel):
    id: int
    episode_number: str
    status: str
    progress: float
    speed_bps: int


class ScheduleResponse(BaseModel):
    id: int
    anime_id: int
    anime_slug: str
    anime_title: str
    cover_url: str | None
    source_site: str
    dest_folder: str
    filename_template: str
    filename_template_type: str
    enabled: bool
    last_run_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    current_episode: int = 0
    active_downloads: list[ActiveDownload] = []

    model_config = {"from_attributes": True}


class ScheduleListResponse(BaseModel):
    scheduled: list[ScheduleResponse]
    cron_expr: str
    next_run_at: datetime | None


class CronValidationResponse(BaseModel):
    valid: bool
    next_runs: list[datetime] = []
    error: str | None = None


class CronUpdateRequest(BaseModel):
    cron_expr: str


class RunNowResponse(BaseModel):
    enqueued_episodes: int
    skipped_reason: str | None = None


class RunAllNowResponse(BaseModel):
    total_enqueued: int
