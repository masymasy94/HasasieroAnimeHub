"""Scheduled download service — cron-driven recurring auto-downloads."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..config import settings
from ..models.scheduled_download import ScheduledDownload
from ..schemas.download import DownloadRequest, EpisodeDownloadRequest
from ..schemas.scheduled import ScheduleCreate, ScheduleUpdate
from ..utils.episode_scanner import highest_episode
from ..utils.safe_path import PathOutsideBaseError, resolve_inside
from .download_service import DownloadService
from .providers import ProviderRegistry

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60


class ScheduledDownloadService:
    def __init__(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        provider_registry: ProviderRegistry,
        download_service: DownloadService,
    ) -> None:
        self._db = db_session_factory
        self._registry = provider_registry
        self._download_service = download_service
        self._task: asyncio.Task | None = None
        self._base_dir = Path(settings.download_dir)

    # ── lifecycle ──

    def start(self) -> None:
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduled download service started")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduled download service stopped")

    # ── CRUD ──

    async def list_all(self) -> list[ScheduledDownload]:
        async with self._db() as session:
            result = await session.execute(
                select(ScheduledDownload).order_by(ScheduledDownload.anime_title)
            )
            return list(result.scalars().all())

    async def get(self, schedule_id: int) -> ScheduledDownload | None:
        async with self._db() as session:
            return await session.get(ScheduledDownload, schedule_id)

    async def create(self, request: ScheduleCreate) -> ScheduledDownload:
        self._validate_cron(request.cron_expr)
        self._validate_dest_folder(request.dest_folder)
        async with self._db() as session:
            row = ScheduledDownload(
                anime_id=request.anime_id,
                anime_slug=request.anime_slug,
                anime_title=request.anime_title,
                cover_url=request.cover_url,
                source_site=request.source_site,
                dest_folder=request.dest_folder,
                filename_template=request.filename_template,
                filename_template_type=request.filename_template_type,
                cron_expr=request.cron_expr,
                enabled=int(request.enabled),
                next_run_at=self._next_run(request.cron_expr, datetime.now()),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def update(
        self, schedule_id: int, update: ScheduleUpdate
    ) -> ScheduledDownload | None:
        async with self._db() as session:
            row = await session.get(ScheduledDownload, schedule_id)
            if not row:
                return None
            if update.dest_folder is not None:
                self._validate_dest_folder(update.dest_folder)
                row.dest_folder = update.dest_folder
            if update.filename_template is not None:
                row.filename_template = update.filename_template
            if update.filename_template_type is not None:
                row.filename_template_type = update.filename_template_type
            if update.cron_expr is not None:
                self._validate_cron(update.cron_expr)
                row.cron_expr = update.cron_expr
                row.next_run_at = self._next_run(update.cron_expr, datetime.now())
            if update.enabled is not None:
                row.enabled = int(update.enabled)
            row.updated_at = datetime.now()
            await session.commit()
            await session.refresh(row)
            return row

    async def delete(self, schedule_id: int) -> bool:
        async with self._db() as session:
            row = await session.get(ScheduledDownload, schedule_id)
            if not row:
                return False
            await session.delete(row)
            await session.commit()
            return True

    # ── validation helpers ──

    @staticmethod
    def _validate_cron(expr: str) -> None:
        if not croniter.is_valid(expr):
            raise ValueError(f"Invalid cron expression: {expr!r}")

    def _validate_dest_folder(self, folder: str) -> None:
        try:
            resolve_inside(self._base_dir, folder)
        except PathOutsideBaseError as exc:
            raise ValueError(str(exc)) from exc

    @staticmethod
    def _next_run(cron_expr: str, base_time: datetime) -> datetime:
        return croniter(cron_expr, base_time).get_next(datetime)

    # ── run loop ──

    async def _run_loop(self) -> None:
        """Every minute, find schedules whose next_run_at has passed and run them."""
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Scheduled loop error: %s", exc)
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)

    async def _tick(self) -> None:
        now = datetime.now()
        async with self._db() as session:
            result = await session.execute(
                select(ScheduledDownload).where(ScheduledDownload.enabled == 1)
            )
            rows = list(result.scalars().all())

        for row in rows:
            if row.next_run_at is not None and now < row.next_run_at:
                continue
            try:
                enqueued, reason = await self._execute(row.id)
                logger.info(
                    "Schedule %d (%s): enqueued %d episodes%s",
                    row.id,
                    row.anime_title,
                    enqueued,
                    f" — {reason}" if reason else "",
                )
            except Exception as exc:
                logger.error("Schedule %d failed: %s", row.id, exc)
                async with self._db() as session:
                    fresh = await session.get(ScheduledDownload, row.id)
                    if fresh:
                        fresh.last_error = str(exc)
                        fresh.last_run_at = datetime.now()
                        fresh.next_run_at = self._next_run(
                            fresh.cron_expr, datetime.now()
                        )
                        await session.commit()

    async def run_now(self, schedule_id: int) -> tuple[int, str | None]:
        return await self._execute(schedule_id)

    async def _execute(self, schedule_id: int) -> tuple[int, str | None]:
        """Run one schedule. Returns (enqueued_count, skipped_reason)."""
        async with self._db() as session:
            row = await session.get(ScheduledDownload, schedule_id)
            if not row:
                return (0, "schedule not found")
            snapshot = {
                "id": row.id,
                "anime_id": row.anime_id,
                "anime_slug": row.anime_slug,
                "anime_title": row.anime_title,
                "cover_url": row.cover_url,
                "source_site": row.source_site,
                "dest_folder": row.dest_folder,
                "filename_template": row.filename_template,
                "filename_template_type": row.filename_template_type,
                "cron_expr": row.cron_expr,
            }

        # Determine highest episode already on disk.
        try:
            dest = resolve_inside(self._base_dir, snapshot["dest_folder"])
        except PathOutsideBaseError as exc:
            await self._mark_run(snapshot["id"], error=str(exc))
            return (0, str(exc))

        current_highest = highest_episode(dest)

        # Ask provider for episodes after current_highest.
        try:
            provider = self._registry.get(snapshot["source_site"])
        except ValueError as exc:
            await self._mark_run(snapshot["id"], error=str(exc))
            return (0, str(exc))

        episodes, _total = await provider.get_episodes(
            snapshot["anime_id"],
            snapshot["anime_slug"],
            start=current_highest + 1,
        )

        if not episodes:
            await self._mark_run(snapshot["id"], error=None)
            return (0, "no new episodes")

        request = DownloadRequest(
            anime_id=snapshot["anime_id"],
            anime_title=snapshot["anime_title"],
            anime_slug=snapshot["anime_slug"],
            cover_url=snapshot["cover_url"],
            source_site=snapshot["source_site"],
            episodes=[
                EpisodeDownloadRequest(
                    episode_id=ep.id,
                    episode_number=ep.number,
                    episode_title=ep.title,
                )
                for ep in episodes
            ],
            dest_folder_override=snapshot["dest_folder"],
            filename_template=snapshot["filename_template"],
            filename_template_type=snapshot["filename_template_type"],
            scheduled_download_id=snapshot["id"],
        )
        downloads = await self._download_service.enqueue(request)

        await self._mark_run(snapshot["id"], error=None)
        return (len(downloads), None)

    async def _mark_run(self, schedule_id: int, *, error: str | None) -> None:
        async with self._db() as session:
            row = await session.get(ScheduledDownload, schedule_id)
            if not row:
                return
            row.last_run_at = datetime.now()
            row.last_error = error
            row.next_run_at = self._next_run(row.cron_expr, datetime.now())
            row.updated_at = datetime.now()
            await session.commit()
