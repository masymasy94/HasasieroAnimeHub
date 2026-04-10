import asyncio
import logging
import time
from collections.abc import Callable
from pathlib import Path

from .metadata_service import MetadataService
from .providers import ProviderRegistry
from .providers.base import VideoSource
from ..utils.filename import episode_filename, extract_season

logger = logging.getLogger(__name__)

CHUNK_SIZE = 128 * 1024  # 128KB
MIN_VIDEO_SIZE = 50 * 1024  # 50KB – anything smaller is certainly not a real video
VALID_VIDEO_CONTENT_TYPES = {"video/", "application/octet-stream", "binary/octet-stream"}

# Stream-level retry settings (for connection drops during download)
MAX_STREAM_RETRIES = 5
STREAM_RETRY_BASE_DELAY = 5  # seconds (5, 10, 15, …)
STREAM_TIMEOUT = 300  # 5 minutes — large files on slow connections need headroom
STALL_TIMEOUT = 60  # seconds with no data before we consider the stream dead

# HLS segment retry
MAX_SEGMENT_RETRIES = 3
SEGMENT_RETRY_DELAY = 3  # seconds


class DownloadWorker:
    """Handles downloading a single episode file with progress tracking."""

    def __init__(
        self,
        provider_registry: ProviderRegistry,
        metadata_service: MetadataService,
    ):
        self._registry = provider_registry
        self._metadata = metadata_service

    async def download_episode(
        self,
        episode_id: int,
        episode_number: str,
        anime_title: str,
        anime_slug: str,
        download_dir: Path,
        progress_callback: Callable | None = None,
        cover_url: str | None = None,
        genres: list[str] | None = None,
        plot: str | None = None,
        year: str | None = None,
        total_episodes: int = 100,
        source_site: str = "animeunity",
        episode_title: str | None = None,
        dest_folder_override: str | None = None,
        filename_template: str | None = None,
        filename_template_type: str | None = None,
    ) -> Path:
        """
        Download a single episode:
        1. Resolve video URL (JIT)
        2. Download MP4
        3. Embed metadata
        Returns the final file path.

        When `dest_folder_override` + `filename_template` + `filename_template_type`
        are all supplied, the file is written under
        ``download_dir / dest_folder_override / rendered_filename`` instead of
        the Plex-style ``Show/Season NN/...`` layout.
        """
        from ..utils.pattern import PatternInputs, render_filename

        # Resolve video URL just-in-time via the appropriate site provider
        provider = self._registry.get(source_site)
        source = await provider.resolve_download_url(episode_id)

        # Determine file path
        use_override = (
            dest_folder_override is not None
            and filename_template is not None
            and filename_template_type is not None
        )
        if use_override:
            show_name, season = extract_season(anime_title)
            rendered = render_filename(
                template=filename_template,
                template_type=filename_template_type,
                inputs=PatternInputs(
                    anime_title=show_name,
                    season=season,
                    episode_number=episode_number,
                    episode_title=episode_title,
                    total_episodes=total_episodes,
                    extension="mp4",
                ),
            )
            rel_folder = dest_folder_override.lstrip("/")
            final_path = download_dir / rel_folder / rendered
        else:
            relative_path = episode_filename(
                anime_title, episode_number, total_episodes, episode_title
            )
            final_path = download_dir / relative_path
        final_path.parent.mkdir(parents=True, exist_ok=True)

        # Download based on source type
        if source.type == "direct_mp4":
            raw_path = final_path.with_suffix(".mp4.raw")
            await self._download_mp4(source, raw_path, progress_callback)
        else:
            # M3U8/HLS - download and convert
            raw_path = final_path.with_suffix(".mp4.raw")
            await self._download_m3u8(source, raw_path, progress_callback)

        # Embed metadata
        show_name, season = extract_season(anime_title)
        meta_title = f"{show_name} - S{season:02d}E{episode_number}"
        if episode_title:
            meta_title += f" - {episode_title}"
        metadata_ok = await self._metadata.embed_metadata(
            input_path=raw_path,
            output_path=final_path,
            title=meta_title,
            show=show_name,
            episode_number=episode_number,
            genres=genres,
            year=year,
            description=plot,
            cover_url=cover_url,
        )

        if not metadata_ok:
            # Metadata failed, just rename raw file
            logger.warning("Metadata embedding failed, using raw file")
            if raw_path.exists():
                raw_path.rename(final_path)

        return final_path

    async def _download_mp4(
        self,
        source: VideoSource,
        dest_path: Path,
        progress_callback: Callable | None,
    ) -> None:
        """Download a direct MP4 file with dedicated session and stream-level resume.

        Each download attempt creates its own isolated curl-cffi session so that
        shared-session lifecycle events (CSRF refresh, connection pool reuse)
        cannot corrupt the streaming file descriptor.
        """
        from curl_cffi.requests import AsyncSession

        part_path = dest_path.with_suffix(dest_path.suffix + ".part")
        total_bytes = 0

        for attempt in range(1, MAX_STREAM_RETRIES + 1):
            start_byte = part_path.stat().st_size if part_path.exists() else 0

            headers = dict(source.headers) if source.headers else {}
            if start_byte > 0:
                headers["Range"] = f"bytes={start_byte}-"

            # Dedicated session per attempt — never shares fds with the provider
            stream_session = AsyncSession(
                impersonate="chrome", timeout=STREAM_TIMEOUT
            )
            try:
                response = await stream_session.get(
                    source.url, headers=headers, stream=True
                )

                status_code = response.status_code
                if status_code >= 400:
                    raise DownloadError(
                        f"Server returned HTTP {status_code} (expected 200/206)"
                    )

                content_type = response.headers.get("Content-Type", "").lower()
                if "text/html" in content_type:
                    raise DownloadError(
                        f"Server returned HTML instead of video "
                        f"(Content-Type: {content_type}, HTTP {status_code})"
                    )

                # Server ignored Range header — must restart from scratch
                if start_byte > 0 and status_code == 200:
                    logger.info("Server ignored Range header, restarting download")
                    start_byte = 0
                    if part_path.exists():
                        part_path.unlink()

                # Determine total size (first successful response wins)
                if total_bytes == 0:
                    content_range = response.headers.get("Content-Range", "")
                    if content_range and "/" in content_range:
                        total_bytes = int(content_range.split("/")[-1])
                    elif start_byte == 0:
                        total_bytes = int(
                            response.headers.get("Content-Length", "0")
                        )

                downloaded = start_byte
                last_report = time.monotonic()
                last_bytes = downloaded

                mode = "ab" if start_byte > 0 and status_code == 206 else "wb"
                with open(part_path, mode) as f:
                    chunk_iter = response.aiter_content().__aiter__()
                    while True:
                        try:
                            chunk = await asyncio.wait_for(
                                chunk_iter.__anext__(), timeout=STALL_TIMEOUT
                            )
                        except StopAsyncIteration:
                            break
                        except asyncio.TimeoutError:
                            raise TimeoutError(
                                f"Stream stalled — no data for {STALL_TIMEOUT}s "
                                f"(downloaded {downloaded} bytes so far)"
                            )
                        f.write(chunk)
                        downloaded += len(chunk)

                        now = time.monotonic()
                        elapsed = now - last_report
                        if elapsed >= 0.5 and progress_callback:
                            speed = int((downloaded - last_bytes) / elapsed)
                            progress = (
                                (downloaded / total_bytes * 100)
                                if total_bytes
                                else 0
                            )
                            await progress_callback(
                                downloaded_bytes=downloaded,
                                total_bytes=total_bytes,
                                speed_bps=speed,
                                progress=progress,
                            )
                            last_report = now
                            last_bytes = downloaded

                # Stream completed successfully
                break

            except DownloadError:
                raise  # HTTP 4xx / HTML responses — not retryable at stream level

            except Exception as exc:
                current_size = (
                    part_path.stat().st_size if part_path.exists() else 0
                )
                if attempt < MAX_STREAM_RETRIES:
                    delay = STREAM_RETRY_BASE_DELAY * attempt
                    logger.warning(
                        "Stream interrupted at %d bytes (attempt %d/%d): %s "
                        "— resuming in %ds",
                        current_size,
                        attempt,
                        MAX_STREAM_RETRIES,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    raise DownloadError(
                        f"Stream failed after {MAX_STREAM_RETRIES} attempts: {exc}"
                    )
            finally:
                try:
                    await stream_session.close()
                except Exception:
                    pass

        # Validate downloaded file size
        actual_size = part_path.stat().st_size
        if actual_size < MIN_VIDEO_SIZE:
            part_path.unlink(missing_ok=True)
            raise DownloadError(
                f"Downloaded file too small ({actual_size} bytes), "
                f"likely an error page or empty response"
            )

        # Final progress report
        if progress_callback:
            await progress_callback(
                downloaded_bytes=actual_size,
                total_bytes=total_bytes or actual_size,
                speed_bps=0,
                progress=100.0,
            )

        # Rename part to raw
        part_path.rename(dest_path)

    async def _download_m3u8(
        self,
        source: VideoSource,
        dest_path: Path,
        progress_callback: Callable | None,
    ) -> None:
        """Download M3U8/HLS stream and convert to MP4.

        Uses a dedicated session and per-segment retry.
        """
        import m3u8
        from curl_cffi.requests import AsyncSession

        headers = dict(source.headers) if source.headers else {}

        session = AsyncSession(impersonate="chrome", timeout=60)
        try:
            # Fetch master playlist
            response = await session.get(source.url, headers=headers)
            playlist = m3u8.loads(response.text, uri=source.url)

            # Select best quality
            if playlist.playlists:
                best = max(
                    playlist.playlists,
                    key=lambda p: p.stream_info.bandwidth or 0,
                )
                response = await session.get(best.absolute_uri, headers=headers)
                playlist = m3u8.loads(response.text, uri=best.absolute_uri)

            segments = playlist.segments
            total_segments = len(segments)
            if total_segments == 0:
                raise ValueError("No segments found in M3U8 playlist")

            # Download all segments to a temp file
            ts_path = dest_path.with_suffix(".ts")
            downloaded_segments = 0

            with open(ts_path, "wb") as f:
                for segment in segments:
                    # Per-segment retry
                    seg_data = await self._download_segment(
                        session, segment.absolute_uri, headers
                    )
                    f.write(seg_data)
                    downloaded_segments += 1

                    if progress_callback:
                        progress = downloaded_segments / total_segments * 100
                        await progress_callback(
                            downloaded_bytes=downloaded_segments,
                            total_bytes=total_segments,
                            speed_bps=0,
                            progress=progress,
                        )
        finally:
            try:
                await session.close()
            except Exception:
                pass

        # Remux TS to MP4 with ffmpeg
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", str(ts_path), "-c", "copy", str(dest_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()

        # Clean up TS file
        ts_path.unlink(missing_ok=True)

        if process.returncode != 0:
            raise RuntimeError("ffmpeg remux failed")

    @staticmethod
    async def _download_segment(
        session, url: str, headers: dict
    ) -> bytes:
        """Download a single HLS segment with retry."""
        for attempt in range(1, MAX_SEGMENT_RETRIES + 1):
            try:
                response = await session.get(url, headers=headers)
                return response.content
            except Exception as exc:
                if attempt < MAX_SEGMENT_RETRIES:
                    logger.warning(
                        "Segment download failed (attempt %d/%d): %s",
                        attempt,
                        MAX_SEGMENT_RETRIES,
                        exc,
                    )
                    await asyncio.sleep(SEGMENT_RETRY_DELAY)
                else:
                    raise


class DownloadError(Exception):
    """Raised when a download fails in a way that may be retried."""
    pass
