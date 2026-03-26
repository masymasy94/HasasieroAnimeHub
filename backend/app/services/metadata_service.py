import asyncio
import logging
import uuid
from pathlib import Path

from .animeunity_client import AnimeUnityClient

logger = logging.getLogger(__name__)


class MetadataService:
    """Embeds metadata and cover art into MP4 files using ffmpeg."""

    def __init__(self, client: AnimeUnityClient):
        self._client = client

    async def embed_metadata(
        self,
        input_path: Path,
        output_path: Path,
        *,
        title: str,
        show: str,
        episode_number: str,
        genres: list[str] | None = None,
        year: str | None = None,
        description: str | None = None,
        cover_url: str | None = None,
    ) -> bool:
        """
        Embed metadata + cover art into an MP4 file.
        Returns True on success, False on failure (original file preserved).
        """
        cover_path = None

        try:
            # Download cover image if available
            if cover_url:
                cover_path = await self._download_cover(cover_url, input_path.parent)

            # Try with cover first, then without if it fails
            cmd = self._build_ffmpeg_cmd(
                input_path=input_path,
                output_path=output_path,
                cover_path=cover_path,
                title=title,
                show=show,
                episode_number=episode_number,
                genres=genres,
                year=year,
                description=description,
            )

            logger.info("Running ffmpeg for metadata: %s", " ".join(cmd))
            ok = await self._run_ffmpeg(cmd)

            if not ok and cover_path:
                # Retry without cover art (cover might be the issue)
                logger.warning("ffmpeg failed with cover, retrying without cover art")
                output_path.unlink(missing_ok=True)
                cmd = self._build_ffmpeg_cmd(
                    input_path=input_path,
                    output_path=output_path,
                    cover_path=None,
                    title=title,
                    show=show,
                    episode_number=episode_number,
                    genres=genres,
                    year=year,
                    description=description,
                )
                ok = await self._run_ffmpeg(cmd)

            if not ok:
                return False

            # Remove the raw input file
            if input_path != output_path and input_path.exists():
                input_path.unlink()

            logger.info("Metadata embedded successfully: %s", output_path)
            return True

        except Exception as exc:
            logger.error("Metadata embedding failed: %s", exc)
            return False
        finally:
            # Clean up temp cover
            if cover_path and cover_path.exists():
                cover_path.unlink(missing_ok=True)

    async def _run_ffmpeg(self, cmd: list[str]) -> bool:
        """Execute an ffmpeg command. Returns True on success."""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error("ffmpeg failed (rc=%d): %s", process.returncode, stderr.decode(errors="replace")[:500])
            return False
        return True

    async def _download_cover(self, cover_url: str, dest_dir: Path) -> Path | None:
        """Download cover image to a unique temp file."""
        try:
            session = await self._client._ensure_session()
            response = await session.get(cover_url)
            if response.status_code != 200:
                return None

            # Determine extension from content type
            content_type = response.headers.get("content-type", "")
            ext = ".jpg"
            if "png" in content_type:
                ext = ".png"
            elif "webp" in content_type:
                ext = ".webp"

            cover_path = dest_dir / f".cover_{uuid.uuid4().hex[:8]}{ext}"
            cover_path.write_bytes(response.content)
            return cover_path
        except Exception as exc:
            logger.warning("Failed to download cover: %s", exc)
            return None

    def _build_ffmpeg_cmd(
        self,
        input_path: Path,
        output_path: Path,
        cover_path: Path | None,
        title: str,
        show: str,
        episode_number: str,
        genres: list[str] | None,
        year: str | None,
        description: str | None,
    ) -> list[str]:
        cmd = ["ffmpeg", "-y", "-i", str(input_path)]

        # Add cover as input if available
        if cover_path and cover_path.exists():
            cmd.extend(["-i", str(cover_path)])
            cmd.extend(["-map", "0", "-map", "1"])
            # Copy audio/video streams, but re-encode cover as mjpeg
            # (PNG/WebP codecs are not valid inside MP4 containers)
            cmd.extend(["-c", "copy", "-c:v:1", "mjpeg"])
            cmd.extend(["-disposition:v:1", "attached_pic"])
        else:
            cmd.extend(["-map", "0"])
            cmd.extend(["-c", "copy"])

        # Metadata
        cmd.extend(["-metadata", f"title={title}"])
        cmd.extend(["-metadata", f"show={show}"])
        cmd.extend(["-metadata", f"episode_id={episode_number}"])

        try:
            track_num = int(float(episode_number))
            cmd.extend(["-metadata", f"track={track_num}"])
        except (ValueError, TypeError):
            pass

        if genres:
            cmd.extend(["-metadata", f"genre={', '.join(genres)}"])
        if year:
            cmd.extend(["-metadata", f"date={year}"])
        if description:
            desc = description[:1000] if len(description) > 1000 else description
            cmd.extend(["-metadata", f"description={desc}"])

        # Optimize for streaming
        cmd.extend(["-movflags", "+faststart"])

        cmd.append(str(output_path))
        return cmd
