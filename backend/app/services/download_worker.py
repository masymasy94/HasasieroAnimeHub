import asyncio
import json
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
    ) -> Path:
        """
        Download a single episode:
        1. Resolve video URL (JIT)
        2. Download MP4
        3. Embed metadata
        Returns the final file path.
        """
        # Resolve video URL just-in-time via the appropriate site provider
        provider = self._registry.get(source_site)
        source = await provider.resolve_download_url(episode_id)

        # Determine file path
        relative_path = episode_filename(anime_title, episode_number, total_episodes, episode_title)
        final_path = download_dir / relative_path
        final_path.parent.mkdir(parents=True, exist_ok=True)

        # Download based on source type
        if source.type == "direct_mp4":
            raw_path = final_path.with_suffix(".mp4.raw")
            await self._download_mp4(source, raw_path, progress_callback, provider)
        else:
            # M3U8/HLS - download and convert
            raw_path = final_path.with_suffix(".mp4.raw")
            await self._download_m3u8(source, raw_path, progress_callback, provider)

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
        provider=None,
    ) -> None:
        """Download a direct MP4 file with resume support."""
        part_path = dest_path.with_suffix(dest_path.suffix + ".part")

        # Check for existing partial download
        start_byte = 0
        if part_path.exists():
            start_byte = part_path.stat().st_size
            logger.info("Resuming download from byte %d", start_byte)

        headers = dict(source.headers) if source.headers else {}
        if start_byte > 0:
            headers["Range"] = f"bytes={start_byte}-"

        session = await provider.get_http_session()
        response = await session.get(source.url, headers=headers, stream=True)

        # Validate HTTP response status
        status_code = response.status_code
        if status_code >= 400:
            raise DownloadError(
                f"Server returned HTTP {status_code} "
                f"(expected 200/206)"
            )

        # Validate content-type (reject HTML error pages)
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" in content_type:
            raise DownloadError(
                f"Server returned HTML instead of video "
                f"(Content-Type: {content_type}, HTTP {status_code})"
            )

        # Get total size
        total_bytes = 0
        content_range = response.headers.get("Content-Range", "")
        if content_range and "/" in content_range:
            total_bytes = int(content_range.split("/")[-1])
        elif start_byte == 0:
            content_length = response.headers.get("Content-Length", "0")
            total_bytes = int(content_length)

        downloaded = start_byte
        last_report = time.monotonic()
        last_bytes = downloaded

        mode = "ab" if start_byte > 0 else "wb"
        with open(part_path, mode) as f:
            async for chunk in response.aiter_content():
                f.write(chunk)
                downloaded += len(chunk)

                now = time.monotonic()
                elapsed = now - last_report
                if elapsed >= 0.5 and progress_callback:
                    speed = int((downloaded - last_bytes) / elapsed)
                    progress = (downloaded / total_bytes * 100) if total_bytes else 0
                    await progress_callback(
                        downloaded_bytes=downloaded,
                        total_bytes=total_bytes,
                        speed_bps=speed,
                        progress=progress,
                    )
                    last_report = now
                    last_bytes = downloaded

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
                downloaded_bytes=downloaded,
                total_bytes=total_bytes,
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
        provider=None,
    ) -> None:
        """Download M3U8/HLS stream and convert to MP4."""
        import m3u8

        headers = dict(source.headers) if source.headers else {}
        session = await provider.get_http_session()

        # Fetch master playlist
        response = await session.get(source.url, headers=headers)
        playlist = m3u8.loads(response.text, uri=source.url)

        # Select best quality
        if playlist.playlists:
            # Sort by bandwidth (highest first)
            best = max(playlist.playlists, key=lambda p: p.stream_info.bandwidth or 0)
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
                seg_response = await session.get(segment.absolute_uri, headers=headers)
                f.write(seg_response.content)
                downloaded_segments += 1

                if progress_callback:
                    progress = downloaded_segments / total_segments * 100
                    await progress_callback(
                        downloaded_bytes=downloaded_segments,
                        total_bytes=total_segments,
                        speed_bps=0,
                        progress=progress,
                    )

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


class DownloadError(Exception):
    """Raised when a download fails in a way that may be retried."""
    pass
