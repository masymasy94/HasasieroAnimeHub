import asyncio
import json
import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..models.download import Download
from ..models.setting import Setting
from ..schemas.download import DownloadRequest
from .download_worker import DownloadWorker
from .metadata_service import MetadataService
from .nas_queue import NasIOQueue
from .nfo_service import write_episode_nfo, write_tvshow_nfo
from .providers import ProviderRegistry
from .ws_manager import WebSocketManager
from ..utils.filename import extract_season

logger = logging.getLogger(__name__)

MAX_AUTO_RETRIES = 3
RETRY_BACKOFF_BASE = 30  # seconds between retries (30, 60, 90)

# DB write retry settings for SQLite contention
_DB_WRITE_ATTEMPTS = 5
_DB_WRITE_BACKOFF = 0.3  # seconds

# Local temp directory — downloads + ffmpeg happen here, then move to NAS
LOCAL_TEMP_DIR = Path(tempfile.gettempdir()) / "animehub"


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
    """Manages the download queue, spawns workers, enforces concurrency limits.

    Downloads happen to a local temp directory first (fast I/O), then files
    are moved to the NAS via NasIOQueue so the event loop is never blocked.
    """

    def __init__(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        provider_registry: ProviderRegistry,
        metadata_service: MetadataService,
        ws_manager: WebSocketManager,
        nas_queue: NasIOQueue,
        download_dir: Path,
        max_concurrent: int = 2,
    ):
        self._db = db_session_factory
        self._registry = provider_registry
        self._worker = DownloadWorker(provider_registry, metadata_service)
        self._ws = ws_manager
        self._nas_queue = nas_queue
        self._download_dir = download_dir
        self._local_temp = LOCAL_TEMP_DIR
        self._default_max_concurrent = max_concurrent
        self._active_tasks: dict[int, asyncio.Task] = {}
        self._worker_task: asyncio.Task | None = None

    def start(self) -> None:
        self._local_temp.mkdir(parents=True, exist_ok=True)
        self._worker_task = asyncio.create_task(self._worker_loop())
        asyncio.create_task(self._reset_stale_statuses())
        logger.info(
            "Download worker started (max concurrent: %d, local temp: %s)",
            self._default_max_concurrent,
            self._local_temp,
        )

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

    async def _reset_stale_statuses(self) -> None:
        """Reset downloads stuck in transient states from a previous crash."""
        try:
            async with self._db() as session:
                result = await session.execute(
                    update(Download)
                    .where(Download.status.in_(["downloading", "finalizing"]))
                    .values(
                        status="queued",
                        progress=0.0,
                        downloaded_bytes=0,
                        total_bytes=0,
                        speed_bps=0,
                        started_at=None,
                    )
                )
                await session.commit()
                if result.rowcount > 0:
                    logger.info(
                        "Reset %d stale downloads to queued", result.rowcount
                    )
        except Exception as exc:
            logger.error("Failed to reset stale statuses: %s", exc)

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
                    dest_folder_override=request.dest_folder_override,
                    filename_template=request.filename_template,
                    filename_template_type=request.filename_template_type,
                    scheduled_download_id=request.scheduled_download_id,
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
            query = query.order_by(
                Download.status.desc(),
                Download.created_at.desc(),
            )
            result = await session.execute(query)
            downloads = list(result.scalars().all())

        status_order = {
            "downloading": 0,
            "finalizing": 1,
            "queued": 2,
            "failed": 3,
            "cancelled": 4,
            "completed": 5,
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
        """Download an episode to local temp, then enqueue NAS move."""
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
                "dest_folder_override": download.dest_folder_override,
                "filename_template": download.filename_template,
                "filename_template_type": download.filename_template_type,
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
                await self._ws.broadcast({
                    "type": "progress",
                    "download_id": dl_info["id"],
                    "progress": round(progress, 1),
                    "downloaded_bytes": downloaded_bytes,
                    "total_bytes": total_bytes,
                    "speed_bps": speed_bps,
                })

            # --- Download to LOCAL temp (fast, no NAS I/O) ---
            local_path = await self._worker.download_episode(
                episode_id=dl_info["episode_id"],
                episode_number=dl_info["episode_number"],
                episode_title=dl_info["episode_title"],
                anime_title=dl_info["anime_title"],
                anime_slug=dl_info["anime_slug"],
                download_dir=self._local_temp,
                progress_callback=on_progress,
                cover_url=dl_info["cover_url"],
                genres=dl_info["genres"],
                plot=dl_info["plot"],
                year=dl_info["year"],
                source_site=dl_info["source_site"],
                dest_folder_override=dl_info["dest_folder_override"],
                filename_template=dl_info["filename_template"],
                filename_template_type=dl_info["filename_template_type"],
            )

            # --- Validate file locally (fast, no NAS) ---
            file_size = local_path.stat().st_size
            if file_size < 50 * 1024:
                local_path.unlink(missing_ok=True)
                raise RuntimeError(
                    f"Output file too small ({file_size} bytes)"
                )

            # --- Compute NAS destination ---
            relative = local_path.relative_to(self._local_temp)
            nas_path = self._download_dir / relative

            # --- Set status to "finalizing" and release download slot ---
            await _db_execute_with_retry(
                self._db,
                update(Download)
                .where(Download.id == dl_info["id"])
                .values(status="finalizing", progress=100.0),
            )

            await self._ws.broadcast({
                "type": "status_change",
                "download_id": dl_info["id"],
                "status": "finalizing",
            })

            logger.info(
                "Download done locally, enqueueing NAS move: %s EP%s",
                dl_info["anime_title"],
                dl_info["episode_number"],
            )

            # --- Enqueue non-blocking NAS move ---
            async def on_move_success(final_path: Path) -> None:
                # Write Kodi-style NFO sidecars at the NAS destination so
                # Jellyfin can read them. NFOs are written here (post-move)
                # rather than in the worker because the worker writes into
                # local temp; the NAS queue only moves the .mp4.
                show_name, season = extract_season(dl_info["anime_title"])
                write_episode_nfo(
                    final_path,
                    show=show_name,
                    season=season,
                    episode_number=dl_info["episode_number"],
                    episode_title=dl_info["episode_title"],
                    plot=dl_info["plot"],
                )
                show_root = (
                    final_path.parent.parent
                    if final_path.parent.name.lower().startswith("season ")
                    else final_path.parent
                )
                write_tvshow_nfo(
                    show_root,
                    title=show_name,
                    plot=dl_info["plot"],
                    year=dl_info["year"],
                    genres=dl_info["genres"],
                )

                await _db_execute_with_retry(
                    self._db,
                    update(Download)
                    .where(Download.id == dl_info["id"])
                    .values(
                        status="completed",
                        file_path=str(final_path),
                        completed_at=datetime.utcnow(),
                    ),
                )
                await self._ws.broadcast({
                    "type": "status_change",
                    "download_id": dl_info["id"],
                    "status": "completed",
                    "file_path": str(final_path),
                    "completed_at": datetime.utcnow().isoformat(),
                })
                logger.info(
                    "NAS move completed: %s EP%s -> %s",
                    dl_info["anime_title"],
                    dl_info["episode_number"],
                    final_path,
                )

            async def on_move_failure(exc: Exception) -> None:
                # Clean up local temp file
                try:
                    local_path.unlink(missing_ok=True)
                except Exception:
                    pass
                await _db_execute_with_retry(
                    self._db,
                    update(Download)
                    .where(Download.id == dl_info["id"])
                    .values(
                        status="failed",
                        error_message=f"NAS move failed: {exc}",
                    ),
                )
                await self._ws.broadcast({
                    "type": "error",
                    "download_id": dl_info["id"],
                    "status": "failed",
                    "error_message": f"NAS move failed: {exc}",
                })
                logger.error(
                    "NAS move failed for %s EP%s: %s",
                    dl_info["anime_title"],
                    dl_info["episode_number"],
                    exc,
                )

            await self._nas_queue.enqueue_move(
                local_path=local_path,
                nas_path=nas_path,
                on_success=on_move_success,
                on_failure=on_move_failure,
            )
            # Download slot is released here — NAS move proceeds independently

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

            # Clean up partial files from local temp
            self._cleanup_partial_files(dl_info["anime_title"], dl_info["episode_number"])

            if retry_count < MAX_AUTO_RETRIES:
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

                await asyncio.sleep(wait)
            else:
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
            # Clean from local temp (where downloads happen now)
            base_path = self._local_temp / relative_path
            parent = base_path.parent

            if not parent.exists():
                return

            stem = base_path.stem
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
