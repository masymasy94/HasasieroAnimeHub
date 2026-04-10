from pathlib import Path

from app.utils.episode_scanner import highest_episode


def test_empty_folder_returns_zero(tmp_path: Path) -> None:
    assert highest_episode(tmp_path) == 0


def test_nonexistent_folder_returns_zero(tmp_path: Path) -> None:
    assert highest_episode(tmp_path / "missing") == 0


def test_picks_max_from_plex_style_names(tmp_path: Path) -> None:
    for name in [
        "One Piece - S01E001.mp4",
        "One Piece - S01E002.mp4",
        "One Piece - S01E010.mp4",
    ]:
        (tmp_path / name).write_bytes(b"")
    assert highest_episode(tmp_path) == 10


def test_picks_max_from_custom_suffix_names(tmp_path: Path) -> None:
    for name in ["OP 01.mp4", "OP 02.mp4", "OP 05.mp4"]:
        (tmp_path / name).write_bytes(b"")
    assert highest_episode(tmp_path) == 5


def test_mixed_names(tmp_path: Path) -> None:
    (tmp_path / "Show - S01E004.mp4").write_bytes(b"")
    (tmp_path / "Show 07.mp4").write_bytes(b"")
    (tmp_path / "random.txt").write_bytes(b"")
    assert highest_episode(tmp_path) == 7


def test_ignores_non_video_extensions(tmp_path: Path) -> None:
    (tmp_path / "Show - S01E003.srt").write_bytes(b"")
    (tmp_path / "Show - S01E002.mp4").write_bytes(b"")
    assert highest_episode(tmp_path) == 2


def test_recurses_into_season_subfolders(tmp_path: Path) -> None:
    season = tmp_path / "Season 01"
    season.mkdir()
    (season / "Show - S01E006.mp4").write_bytes(b"")
    assert highest_episode(tmp_path) == 6


def test_underscore_ep_pattern(tmp_path: Path) -> None:
    """Matches filenames like KoorinoJouheki_Ep_01_SUB_ITA.mp4"""
    (tmp_path / "KoorinoJouheki_Ep_01_SUB_ITA.mp4").write_bytes(b"")
    (tmp_path / "KoorinoJouheki_Ep_03_SUB_ITA.mp4").write_bytes(b"")
    assert highest_episode(tmp_path) == 3


def test_dot_separated_ep_pattern(tmp_path: Path) -> None:
    """Matches filenames like Show.Ep.05.mp4"""
    (tmp_path / "Show.Ep.05.mp4").write_bytes(b"")
    assert highest_episode(tmp_path) == 5
