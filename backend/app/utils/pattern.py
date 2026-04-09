"""Filename template rendering for scheduled downloads.

Two template types:

* ``preset`` — the template contains placeholders and is rendered with
  :func:`str.format_map`. Known placeholders: ``{anime}``, ``{season}``,
  ``{episode}``, ``{ep_title}``, ``{ext}``.
* ``custom`` — the template is a user-supplied filename stem. The
  rendered filename appends a space and the zero-padded episode number
  followed by ``.{ext}``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .filename import sanitize_filename

PATTERN_PRESETS: dict[str, str] = {
    "plex_default": "{anime} - S{season}E{episode} - {ep_title}.{ext}",
    "episode_only": "{episode}.{ext}",
    "anime_and_episode": "{anime} - {episode}.{ext}",
}


@dataclass
class PatternInputs:
    anime_title: str
    season: int
    episode_number: str
    episode_title: str | None
    total_episodes: int
    extension: str = "mp4"


def _padding_width(total_episodes: int) -> int:
    if total_episodes >= 1000:
        return 4
    if total_episodes >= 100:
        return 3
    return 2


def _format_episode(episode_number: str, width: int) -> str:
    try:
        return f"{int(float(episode_number)):0{width}d}"
    except (ValueError, TypeError):
        return sanitize_filename(str(episode_number))


def render_filename(
    *,
    template: str,
    template_type: str,
    inputs: PatternInputs,
) -> str:
    """Return the final filename (single path component, no directory)."""
    width = _padding_width(inputs.total_episodes)
    ep = _format_episode(inputs.episode_number, width)

    if template_type == "preset":
        rendered = template.format_map(
            {
                "anime": sanitize_filename(inputs.anime_title),
                "season": f"{inputs.season:02d}",
                "episode": ep,
                "ep_title": sanitize_filename(inputs.episode_title or ""),
                "ext": inputs.extension,
            }
        )
        # Preset may leave " -  - " when ep_title is empty; tidy up.
        rendered = re.sub(r"\s+-\s+-\s+", " - ", rendered)
        rendered = rendered.strip(" -")
        return sanitize_filename(rendered, max_length=240)

    if template_type == "custom":
        stem = template.strip()
        # Drop any extension the user typed — we control it.
        stem = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", stem)
        stem = sanitize_filename(stem)
        return f"{stem} {ep}.{inputs.extension}"

    raise ValueError(f"Unknown template_type: {template_type!r}")
