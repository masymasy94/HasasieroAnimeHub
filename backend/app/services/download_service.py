import asyncio
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..models.download import Download
from ..models.setting import Setting
from ..schemas.download import DownloadRequest
from .download_worker import DownloadWorker
from .metadata_service import MetadataService
from .plex_service import PlexService
from .providers import ProviderRegistry
from .ws_manager import WebSocketManager

logger = logging.getLogger(__name__)

MAX_AUTO_RETRIES = 3
RETRY_BACKOFF_BASE = 30  # seconds between retries (30, 60, 90)

# DB write retry settings for SQLite contention
_DB_WRITE_ATTEMPTS = 5
_DB_WRITE_BACKOFF = 0.3  # seconds


async def _db_execute_with_retry(db_factory, stmt):
    """Execute a DB write with retry on 'database is locked'."""
    for attempt in range(1, _DB_WRITE_ATTEMPTS + 1):
        try:
            async with db_factory() as session:
                await session.execute(stmt)
                await session.commit()
                return
        except Exception as exc:
            if "database is locked" in str(exc) and attempt < _DB_WRITE_ATTEMPTS:
                logger.warning(
                    "DB locked (attempt %d/%d), retrying in %.1fs...",
                    attempt, _DB_WRITE_ATTEMPTS, _DB_WRITE_BACKOFF * attempt,
                )
                await asyncio.sleep(_DB_WRITE_BACKOFF * attempt)
            else:
                raise


class DownloadService:
    """Manages the download queue, spawns workers, enforces concurrency limits."""

    def __init__(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        provider_registry: ProviderRegistry,
        metadata_service: MetadataService,
        ws_manager: WebSocketManager,
        download_dir: Path,
        max_concurrent: int = 2,
    ):
        self._db = db_session_factory
        self._registry = provider_registry
        self._worker = DownloadWorker(provider_registry, metadata_service)
        self._ws = ws_manager
        self._plex = PlexService(db_session_factory)
        self._download_dir = download_dir
        self._default_max_concurrent = max_concurrent
        self._active_tasks: dict[int, asyncio.Task] = {}
        self._worker_task: asyncio.Task | None = None

    def start(self) -> None:
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Download worker started (default max concurrent: %d)", self._default_max_concurrent)

    async def stop(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        for task in self._active_tasks.values():
            task.cancel()

        if self._active_tasks:
            await asyncio.gather(*self._active_tasks.values(), return_exceptions=True)

        self._active_tasks.clear()
        logger.info("Download worker stopped")

    async def enqueue(self, request: DownloadRequest) -> list[Download]:
        downloads = []
        async with self._db() as session:
            for ep in request.episodes:
                download = Download(
                    anime_id=request.anime_id,
                    anime_title=request.anime_title,
                    anime_slug=request.anime_slug,
                    cover_url=request.cover_url,
                    genres=json.dumps(request.genres) if request.genres else None,
                    plot=request.plot,
                    year=request.year,
                    source_site=request.source_site,
                    episode_id=ep.episode_id,
                    episode_number=ep.episode_number,
                    episode_title=ep.episode_title,
                    status="queued",
                )
                session.add(download)
                try:
                    await session.flush()
                    downloads.append(download)
                except Exception:
                    await session.rollback()
                    logger.warning(
                        "Episode %d already in queue for anime %d",
                        ep.episode_id, request.anime_id,
                    )
                    continue
            await session.commit()

        return downloads

    async def get_downloads(self, statuses: list[str] | None = None) -> list[Download]:
        async with self._db() as session:
            query = select(Download)
            if statuses:
                query = query.where(Download.status.in_(statuses))
            # Order: downloading first, then queued, then rest by created_at desc
            query = query.order_by(
                # CASE: downloading=0, queued=1, failed=2, cancelled=3, completed=4
                Download.status.desc(),  # temporary, we sort in Python below
                Download.created_at.desc(),
            )
            result = await session.execute(query)
            downloads = list(result.scalars().all())

        # Custom sort: downloading > queued > failed/cancelled > completed
        status_order = {
            "downloading": 0,
            "queued": 1,
            "failed": 2,
            "cancelled": 3,
            "completed": 4,
        }
        downloads.sort(key=lambda d: (status_order.get(d.status, 99), -d.created_at.timestamp() if d.created_at else 0))
        return downloads

    async def cancel_download(self, download_id: int) -> bool:
        if download_id in self._active_tasks:
            self._active_tasks[download_id].cancel()
            del self._active_tasks[download_id]

        async with self._db() as session:
            result = await session.execute(
                update(Download)
                .where(Download.id == download_id)
                .where(Download.status.in_(["queued", "downloading"]))
                .values(status="cancelled")
            )
            await session.commit()
            return result.rowcount > 0

    async def cancel_all(self) -> int:
        """Cancel all queued and downloading tasks."""
        # Cancel active tasks
        for task in list(self._active_tasks.values()):
            task.cancel()
        self._active_tasks.clear()

        async with self._db() as session:
            result = await session.execute(
                update(Download)
                .where(Download.status.in_(["queued", "downloading"]))
                .values(status="cancelled")
            )
            await session.commit()
            return result.rowcount

    async def clear_completed(self) -> int:
        """Remove all completed, failed, and cancelled downloads from the list."""
        from sqlalchemy import delete as sql_delete
        async with self._db() as session:
            result = await session.execute(
                sql_delete(Download).where(
                    Download.status.in_(["completed", "failed", "cancelled"])
                )
            )
            await session.commit()
            return result.rowcount

    async def retry_download(self, download_id: int) -> bool:
        async with self._db() as session:
            download = await session.get(Download, download_id)
            if not download or download.status not in ("failed", "cancelled"):
                return False
            # Delete old files
            self._cleanup_download_files(download.file_path)
            result = await session.execute(
                update(Download)
                .where(Download.id == download_id)
                .values(
                    status="queued",
                    retry_count=0,
                    progress=0.0,
                    downloaded_bytes=0,
                    total_bytes=0,
                    speed_bps=0,
                    file_path=None,
                    error_message=None,
                    started_at=None,
                    completed_at=None,
                )
            )
            await session.commit()
            return result.rowcount > 0

    async def retry_all_failed(self) -> int:
        """Reset all failed downloads to queued and clear retry count."""
        async with self._db() as session:
            # First, clean up files for all failed downloads
            result = await session.execute(
                select(Download).where(Download.status == "failed")
            )
            failed_downloads = list(result.scalars().all())
            for dl in failed_downloads:
                self._cleanup_download_files(dl.file_path)

            result = await session.execute(
                update(Download)
                .where(Download.status == "failed")
                .values(
                    status="queued",
                    retry_count=0,
                    progress=0.0,
                    downloaded_bytes=0,
                    total_bytes=0,
                    speed_bps=0,
                    file_path=None,
                    error_message=None,
                    started_at=None,
                    completed_at=None,
                )
            )
            await session.commit()
            return result.rowcount

    async def delete_download(self, download_id: int) -> bool:
        if download_id in self._active_tasks:
            self._active_tasks[download_id].cancel()
            del self._active_tasks[download_id]

        async with self._db() as session:
            download = await session.get(Download, download_id)
            if download:
                await session.delete(download)
                await session.commit()
                return True
            return False

    @staticmethod
    def _cleanup_download_files(file_path: str | None) -> None:
        """Remove a download's output file and any partial/raw temp files."""
        if not file_path:
            return
        for path in [
            Path(file_path),
            Path(file_path).with_suffix(".mp4.raw"),
            Path(file_path).with_suffix(".mp4.raw.part"),
            Path(file_path).with_suffix(".mp4.part"),
        ]:
            try:
                if path.exists():
                    path.unlink()
                    logger.info("Cleaned up file: %s", path)
            except Exception as exc:
                logger.warning("Failed to clean up %s: %s", path, exc)

    def get_disk_usage(self) -> dict:
        """Get disk usage info for the download directory."""
        try:
            usage = shutil.disk_usage(self._download_dir)
            return {
                "total_bytes": usage.total,
                "used_bytes": usage.used,
                "free_bytes": usage.free,
                "path": str(self._download_dir),
            }
        except Exception as exc:
            logger.error("Failed to get disk usage: %s", exc)
            return {
                "total_bytes": 0,
                "used_bytes": 0,
                "free_bytes": 0,
                "path": str(self._download_dir),
            }

    async def _maybe_trigger_plex_scan(self) -> None:
        """Trigger Plex library scan when no more queued/downloading items remain."""
        try:
            async with self._db() as session:
                result = await session.execute(
                    select(Download).where(
                        Download.status.in_(["queued", "downloading"])
                    ).limit(1)
                )
                if result.scalars().first() is not None:
                    return  # Still active downloads
            if await self._plex.is_configured():
                await self._plex.trigger_library_scan()
        except Exception as exc:
            logger.error("Plex scan trigger failed: %s", exc)

    async def _get_max_concurrent(self) -> int:
        """Read max concurrent downloads from DB settings, fallback to default."""
        try:
            async with self._db() as session:
                setting = await session.get(Setting, "max_concurrent_downloads")
                if setting:
                    return int(setting.value)
        except Exception:
            pass
        return self._default_max_concurrent

    async def _worker_loop(self) -> None:
        """Continuously poll for queued downloads and spawn workers."""
        while True:
            try:
                max_concurrent = await self._get_max_concurrent()
                active_count = len(self._active_tasks)
                slots_free = max_concurrent - active_count

                if slots_free > 0:
                    async with self._db() as session:
                        result = await session.execute(
                            select(Download)
                            .where(Download.status == "queued")
                            .order_by(Download.created_at)
                            .limit(slots_free)
                        )
                        queued = list(result.scalars().all())

                    for download in queued:
                        if download.id not in self._active_tasks:
                            task = asyncio.create_task(
                                self._download_one(download.id)
                            )
                            self._active_tasks[download.id] = task
                            task.add_done_callback(
                                lambda t, did=download.id: self._active_tasks.pop(did, None)
                            )

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Worker loop error: %s", exc)

            await asyncio.sleep(2)

    async def _download_one(self, download_id: int) -> None:
        """Execute a single download with automatic retry on failure."""
        async with self._db() as session:
            download = await session.get(Download, download_id)
            if not download or download.status != "queued":
                return

            download.status = "downloading"
            download.started_at = datetime.utcnow()
            download.retry_count = download.retry_count or 0
            await session.commit()

            dl_info = {
                "id": download.id,
                "episode_id": download.episode_id,
                "episode_number": download.episode_number,
                "episode_title": download.episode_title,
                "anime_title": download.anime_title,
                "anime_slug": download.anime_slug,
                "cover_url": download.cover_url,
                "genres": json.loads(download.genres) if download.genres else None,
                "plot": download.plot,
                "year": download.year,
                "retry_count": download.retry_count or 0,
                "source_site": download.source_site,
            }

        await self._ws.broadcast({
            "type": "status_change",
            "download_id": dl_info["id"],
            "status": "downloading",
        })

        try:
            async def on_progress(
                downloaded_bytes: int,
                total_bytes: int,
                speed_bps: int,
                progress: float,
            ):
                # Progress is in-memory + WebSocket only — no DB writes
                # This eliminates SQLite WAL contention during concurrent downloads
                await self._ws.broadcast({
                    "type": "progress",
                    "download_id": dl_info["id"],
                    "progress": round(progress, 1),
                    "downloaded_bytes": downloaded_bytes,
                    "total_bytes": total_bytes,
                    "speed_bps": speed_bps,
                })

            file_path = await self._worker.download_episode(
                episode_id=dl_info["episode_id"],
                episode_number=dl_info["episode_number"],
                episode_title=dl_info["episode_title"],
                anime_title=dl_info["anime_title"],
                anime_slug=dl_info["anime_slug"],
                download_dir=self._download_dir,
                progress_callback=on_progress,
                cover_url=dl_info["cover_url"],
                genres=dl_info["genres"],
                plot=dl_info["plot"],
                year=dl_info["year"],
                source_site=dl_info["source_site"],
            )

            # Validate file exists and is a real video.
            # os.sync + re-stat to bypass CIFS/NFS kernel cache that can report
            # stale metadata on soft-mounted network shares.
            import os
            try:
                os.sync()
            except Exception:
                pass
            # Re-open and read first bytes to force a real I/O roundtrip
            verified_size = 0
            try:
                with open(file_path, "rb") as f:
                    header = f.read(8)  # force actual disk read
                    f.seek(0, 2)  # seek to end
                    verified_size = f.tell()
            except OSError:
                verified_size = 0

            if verified_size < 50 * 1024:
                file_path.unlink(missing_ok=True)
                raise RuntimeError(
                    f"Output file missing or too small ({verified_size} bytes) — "
                    f"network storage may have dropped writes"
                )

            await _db_execute_with_retry(
                self._db,
                update(Download)
                .where(Download.id == dl_info["id"])
                .values(
                    status="completed",
                    progress=100.0,
                    file_path=str(file_path),
                    completed_at=datetime.utcnow(),
                ),
            )

            await self._ws.broadcast({
                "type": "status_change",
                "download_id": dl_info["id"],
                "status": "completed",
                "file_path": str(file_path),
                "completed_at": datetime.utcnow().isoformat(),
            })

            logger.info("Download completed: %s EP%s", dl_info["anime_title"], dl_info["episode_number"])

            # Trigger Plex scan if queue is now empty
            await self._maybe_trigger_plex_scan()

        except asyncio.CancelledError:
            await _db_execute_with_retry(
                self._db,
                update(Download)
                .where(Download.id == dl_info["id"])
                .values(status="cancelled"),
            )
            raise

        except Exception as exc:
            error_msg = str(exc)
            retry_count = dl_info["retry_count"]

            # Clean up partial / corrupt files on failure
            self._cleanup_partial_files(dl_info["anime_title"], dl_info["episode_number"])

            if retry_count < MAX_AUTO_RETRIES:
                # Schedule automatic retry
                next_retry = retry_count + 1
                wait = RETRY_BACKOFF_BASE * next_retry
                logger.warning(
                    "Download failed for %s EP%s (attempt %d/%d): %s — retrying in %ds",
                    dl_info["anime_title"], dl_info["episode_number"],
                    next_retry, MAX_AUTO_RETRIES, error_msg, wait,
                )

                await _db_execute_with_retry(
                    self._db,
                    update(Download)
                    .where(Download.id == dl_info["id"])
                    .values(
                        status="queued",
                        progress=0.0,
                        downloaded_bytes=0,
                        total_bytes=0,
                        speed_bps=0,
                        retry_count=next_retry,
                        error_message=f"Retry {next_retry}/{MAX_AUTO_RETRIES}: {error_msg}",
                        started_at=None,
                    ),
                )

                await self._ws.broadcast({
                    "type": "status_change",
                    "download_id": dl_info["id"],
                    "status": "queued",
                    "error_message": f"Retrying ({next_retry}/{MAX_AUTO_RETRIES})...",
                })

                # Wait before retry to let server recover
                await asyncio.sleep(wait)
            else:
                # Max retries exhausted — mark as permanently failed
                logger.error(
                    "Download permanently failed for %s EP%s after %d retries: %s",
                    dl_info["anime_title"], dl_info["episode_number"],
                    MAX_AUTO_RETRIES, error_msg,
                )

                await _db_execute_with_retry(
                    self._db,
                    update(Download)
                    .where(Download.id == dl_info["id"])
                    .values(
                        status="failed",
                        error_message=f"Failed after {MAX_AUTO_RETRIES} retries: {error_msg}",
                    ),
                )

                await self._ws.broadcast({
                    "type": "error",
                    "download_id": dl_info["id"],
                    "status": "failed",
                    "error_message": error_msg,
                })

    def _cleanup_partial_files(self, anime_title: str, episode_number: str) -> None:
        """Remove .part and .raw partial files left by a failed download."""
        from ..utils.filename import episode_filename

        try:
            relative_path = episode_filename(anime_title, episode_number, 100)
            base_path = self._download_dir / relative_path
            parent = base_path.parent

            if not parent.exists():
                return

            stem = base_path.stem  # e.g. "EP001"
            for f in parent.iterdir():
                if f.name.startswith(stem) and (
                    f.suffix == ".part"
                    or f.name.endswith(".raw.part")
                    or f.name.endswith(".raw")
                ):
                    logger.info("Cleaning up partial file: %s", f)
                    f.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Cleanup failed: %s", exc)
