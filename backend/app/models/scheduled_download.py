from datetime import datetime

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ScheduledDownload(Base):
    __tablename__ = "scheduled_downloads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Anime identity
    anime_id: Mapped[int] = mapped_column(Integer, nullable=False)
    anime_slug: Mapped[str] = mapped_column(Text, nullable=False)
    anime_title: Mapped[str] = mapped_column(Text, nullable=False)
    cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Source & destination
    source_site: Mapped[str] = mapped_column(Text, nullable=False)
    dest_folder: Mapped[str] = mapped_column(Text, nullable=False)  # relative to /downloads

    # Filename template
    filename_template: Mapped[str] = mapped_column(Text, nullable=False)
    filename_template_type: Mapped[str] = mapped_column(Text, nullable=False)  # "preset" | "custom"

    # Scheduling
    cron_expr: Mapped[str] = mapped_column(Text, nullable=False)  # e.g. "0 4 * * *"
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
