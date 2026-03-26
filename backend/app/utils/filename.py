import re
import unicodedata


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """Sanitize a string for use as a filesystem name."""
    # Normalize unicode
    name = unicodedata.normalize("NFC", name)
    # Replace invalid chars with underscore
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    # Strip leading/trailing dots and spaces
    name = name.strip(". ")
    # Collapse multiple underscores/spaces
    name = re.sub(r"[_\s]+", " ", name)
    # Truncate
    if len(name) > max_length:
        name = name[:max_length].rstrip()
    return name or "unknown"


_SEASON_RE = [
    re.compile(r"^(.+?)\s+Season\s+(\d+)", re.I),
    re.compile(r"^(.+?)\s+Stagione\s+(\d+)", re.I),
    re.compile(r"^(.+?)\s+(\d+)(?:st|nd|rd|th)\s+Season", re.I),
]


def extract_season(title: str) -> tuple[str, int]:
    """Extract season number from anime title if present.

    Returns (clean_title, season_number). Defaults to season 1.
    """
    for pattern in _SEASON_RE:
        m = pattern.match(title)
        if m:
            return m.group(1).strip(), int(m.group(2))
    return title, 1


def episode_filename(
    anime_title: str,
    episode_number: str,
    total_episodes: int,
    episode_title: str | None = None,
) -> str:
    """Generate a Plex-compatible filename.

    Pattern: Show Name/Season 01/Show Name - S01E001 - Episode Title.mp4
    """
    show_name, season = extract_season(anime_title)
    show = sanitize_filename(show_name)
    season_folder = f"Season {season:02d}"

    pad = 3 if total_episodes >= 100 else 2
    try:
        num = int(float(episode_number))
        ep_tag = f"S{season:02d}E{num:0{pad}d}"
    except (ValueError, TypeError):
        ep_tag = f"S{season:02d}E{sanitize_filename(str(episode_number))}"

    if episode_title:
        title_clean = sanitize_filename(episode_title, max_length=120)
        name = f"{show} - {ep_tag} - {title_clean}"
    else:
        name = f"{show} - {ep_tag}"

    return f"{show}/{season_folder}/{name}.mp4"
