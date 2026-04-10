from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from ..config import settings
from ..schemas.filesystem import BrowseResponse, FolderEntry, MkdirRequest
from ..utils.episode_scanner import highest_episode
from ..utils.safe_path import PathOutsideBaseError, resolve_inside

router = APIRouter()


def _base() -> Path:
    return Path(settings.download_dir)


def _relative_to_base(path: Path) -> str:
    base = _base().resolve()
    try:
        rel = path.resolve().relative_to(base)
    except ValueError:
        return ""
    return str(rel) if str(rel) != "." else ""


@router.get("/filesystem/browse", response_model=BrowseResponse)
async def browse(path: str = Query(default="")) -> BrowseResponse:
    base = _base()
    try:
        target = resolve_inside(base, path)
    except PathOutsideBaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not target.exists():
        raise HTTPException(status_code=404, detail="Folder not found")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Not a directory")

    entries: list[FolderEntry] = []
    for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if child.name.startswith("."):
            continue
        entries.append(
            FolderEntry(
                name=child.name,
                path=_relative_to_base(child),
                is_dir=child.is_dir(),
            )
        )

    current_rel = _relative_to_base(target)
    parent_rel = _relative_to_base(target.parent) if target != base.resolve() else None

    return BrowseResponse(
        current_path=current_rel,
        parent_path=parent_rel,
        entries=entries,
    )


@router.post("/filesystem/mkdir", response_model=BrowseResponse)
async def mkdir(request: MkdirRequest) -> BrowseResponse:
    base = _base()
    try:
        parent = resolve_inside(base, request.parent_path)
    except PathOutsideBaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not parent.is_dir():
        raise HTTPException(status_code=400, detail="Parent is not a directory")

    cleaned_name = request.name.strip().strip("/").strip(".")
    if not cleaned_name or "/" in cleaned_name:
        raise HTTPException(status_code=400, detail="Invalid folder name")

    try:
        new_folder = resolve_inside(base, f"{_relative_to_base(parent)}/{cleaned_name}")
    except PathOutsideBaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    new_folder.mkdir(parents=False, exist_ok=True)
    return await browse(path=_relative_to_base(parent))


@router.get("/filesystem/highest-episode")
async def get_highest_episode(
    path: str = Query(default=""),
    anime_title: str = Query(default=""),
):
    base = _base()
    try:
        target = resolve_inside(base, path)
    except PathOutsideBaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not target.exists() or not target.is_dir():
        return {"highest_episode": 0, "title_match": False}

    ep = highest_episode(target)

    # Check if any video file in the folder contains the anime title.
    # Normalize both sides: strip spaces, underscores, hyphens, dots
    # so "Koori no Jouheki" matches "KoorinoJouheki_Ep_01_SUB_ITA".
    import re
    def _normalize(s: str) -> str:
        return re.sub(r"[\s_.\-]+", "", s).lower()

    title_match = False
    if anime_title:
        needle = _normalize(anime_title)
        from ..utils.episode_scanner import VIDEO_EXTENSIONS
        for f in target.rglob("*"):
            if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                if needle in _normalize(f.stem):
                    title_match = True
                    break

    return {"highest_episode": ep, "title_match": title_match}
