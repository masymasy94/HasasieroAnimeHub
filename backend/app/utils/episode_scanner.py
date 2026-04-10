"""Scan a folder for existing episode files and return the highest number."""
import re
from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}

# Match patterns:
#   "Show - S01E010" / "S01E10"   → captures 10
#   "Show 10" / "Show - 10"       → captures 10
#   "E10" / "EP10" / "Ep 10"      → captures 10
_SE_RE = re.compile(r"[Ss]\d{1,2}[Ee](\d{1,4})")
_EP_RE = re.compile(r"(?:[Ee][Pp]?|[Ee]pisodio)[\s_.-]*(\d{1,4})")
_TRAILING_NUM_RE = re.compile(r"(\d{1,4})(?=\s*\.[^.]+$)")


def highest_episode(folder: Path) -> int:
    """Return the highest episode number found under `folder` (recursive).

    Returns 0 when the folder is missing or no episodes are detected.
    Only files with video extensions are considered.
    """
    if not folder.exists() or not folder.is_dir():
        return 0

    highest = 0
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue

        number = _extract_episode_number(path.name)
        if number is not None and number > highest:
            highest = number

    return highest


def _extract_episode_number(filename: str) -> int | None:
    for regex in (_SE_RE, _EP_RE, _TRAILING_NUM_RE):
        match = regex.search(filename)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                continue
    return None
