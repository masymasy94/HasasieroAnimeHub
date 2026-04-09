import pytest

from app.utils.pattern import (
    PATTERN_PRESETS,
    PatternInputs,
    render_filename,
)


def _inputs(**overrides) -> PatternInputs:
    base = dict(
        anime_title="One Piece",
        season=1,
        episode_number="6",
        episode_title="Mysterious Woman",
        total_episodes=1100,
        extension="mp4",
    )
    base.update(overrides)
    return PatternInputs(**base)


def test_preset_plex_default() -> None:
    out = render_filename(
        template=PATTERN_PRESETS["plex_default"],
        template_type="preset",
        inputs=_inputs(),
    )
    assert out == "One Piece - S01E0006 - Mysterious Woman.mp4"


def test_preset_episode_only() -> None:
    out = render_filename(
        template=PATTERN_PRESETS["episode_only"],
        template_type="preset",
        inputs=_inputs(),
    )
    assert out == "0006.mp4"


def test_preset_anime_and_episode() -> None:
    out = render_filename(
        template=PATTERN_PRESETS["anime_and_episode"],
        template_type="preset",
        inputs=_inputs(),
    )
    assert out == "One Piece - 0006.mp4"


def test_custom_template_appends_episode_number() -> None:
    out = render_filename(
        template="Mio File",
        template_type="custom",
        inputs=_inputs(episode_number="6", total_episodes=12),
    )
    assert out == "Mio File 06.mp4"


def test_custom_template_strips_user_extension() -> None:
    out = render_filename(
        template="Mio File.mp4",
        template_type="custom",
        inputs=_inputs(episode_number="6", total_episodes=12),
    )
    assert out == "Mio File 06.mp4"


def test_custom_template_uses_three_digit_padding_for_hundred_plus_series() -> None:
    out = render_filename(
        template="OP",
        template_type="custom",
        inputs=_inputs(episode_number="6", total_episodes=150),
    )
    assert out == "OP 006.mp4"


def test_custom_template_uses_four_digit_padding_for_thousand_plus_series() -> None:
    out = render_filename(
        template="OP",
        template_type="custom",
        inputs=_inputs(episode_number="6", total_episodes=1100),
    )
    assert out == "OP 0006.mp4"


def test_unknown_template_type_raises() -> None:
    with pytest.raises(ValueError):
        render_filename(
            template="x",
            template_type="bogus",
            inputs=_inputs(),
        )


def test_sanitizes_invalid_chars_in_output() -> None:
    out = render_filename(
        template="Foo/Bar",
        template_type="custom",
        inputs=_inputs(episode_number="6", total_episodes=12),
    )
    # `/` is not a legal filename char on the final component
    assert "/" not in out
    assert out.endswith("06.mp4")
