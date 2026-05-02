"""Kodi-style NFO sidecar generation for Jellyfin/Plex/Kodi compatibility.

Jellyfin doesn't reliably read embedded MP4 metadata for episode titles in
locales without a metadata-provider match (e.g. Italian dubs not in TVDB).
NFO sidecars are the documented, server-agnostic way to ship metadata.
"""
from __future__ import annotations

import logging
from pathlib import Path
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)


def _safe_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _pretty(root: ET.Element) -> bytes:
    ET.indent(root, space="  ")
    return b"<?xml version=\"1.0\" encoding=\"utf-8\"?>\n" + ET.tostring(root, encoding="utf-8")


def write_episode_nfo(
    video_path: Path,
    *,
    show: str,
    season: int,
    episode_number: str,
    episode_title: str | None,
    plot: str | None = None,
    aired: str | None = None,
) -> Path | None:
    """Write a `<basename>.nfo` Kodi episodedetails next to the .mp4.

    Overwrites any existing file. Returns the nfo path on success, None on failure.
    """
    nfo_path = video_path.with_suffix(".nfo")
    ep_int = _safe_int(episode_number)

    root = ET.Element("episodedetails")
    ET.SubElement(root, "title").text = episode_title or f"Episode {episode_number}"
    ET.SubElement(root, "showtitle").text = show
    ET.SubElement(root, "season").text = str(season)
    if ep_int is not None:
        ET.SubElement(root, "episode").text = str(ep_int)
    if plot:
        ET.SubElement(root, "plot").text = plot
    if aired:
        ET.SubElement(root, "aired").text = aired

    try:
        nfo_path.write_bytes(_pretty(root))
        return nfo_path
    except OSError as exc:
        logger.warning("Failed to write episode nfo at %s: %s", nfo_path, exc)
        return None


def write_tvshow_nfo(
    show_dir: Path,
    *,
    title: str,
    plot: str | None = None,
    year: str | None = None,
    genres: list[str] | None = None,
    overwrite: bool = False,
) -> Path | None:
    """Write `tvshow.nfo` at the series root.

    Skips when the file already exists unless `overwrite=True`, so manual
    edits in Jellyfin (e.g. user-locked title) are preserved across new
    episode downloads.
    """
    nfo_path = show_dir / "tvshow.nfo"
    if nfo_path.exists() and not overwrite:
        return nfo_path

    root = ET.Element("tvshow")
    ET.SubElement(root, "title").text = title
    if plot:
        ET.SubElement(root, "plot").text = plot
    if year:
        ET.SubElement(root, "year").text = str(year)
    for genre in genres or []:
        ET.SubElement(root, "genre").text = genre

    try:
        show_dir.mkdir(parents=True, exist_ok=True)
        nfo_path.write_bytes(_pretty(root))
        return nfo_path
    except OSError as exc:
        logger.warning("Failed to write tvshow nfo at %s: %s", nfo_path, exc)
        return None
