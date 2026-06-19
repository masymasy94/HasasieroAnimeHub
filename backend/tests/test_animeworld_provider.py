"""Unit tests for the AnimeWorld provider download resolution (no network).

Regression for the 401/empty-links breakage: the player/download flow must use the
alphanumeric link id (``data-id``, e.g. "Dinwg") cached by get_episodes, NOT the numeric
``data-episode-id`` — and extract the media URL from the serverPlayerAnimeWorld page.
"""
import asyncio

from app.services.providers.animeworld_provider import AnimeWorldProvider

_PLAY_HTML = """
<div class="server" data-name="9">
  <ul>
    <li class="episode"><a data-episode-id="4816" data-id="Dinwg"
        data-episode-num="1" href="/play/hxh/Dinwg">1</a></li>
    <li class="episode"><a data-episode-id="4817" data-id="1kOiC"
        data-episode-num="2" href="/play/hxh/1kOiC">2</a></li>
  </ul>
</div>
"""

_PLAYER_HTML = """
<html><body><video>
<source src="https://cdn.example.org/DDL/ANIME/HunterXHunter/HunterXHunter_Ep_001_SUB_ITA.mp4"
        type="video/mp4">
</video></body></html>
"""


class _FakeResponse:
    def __init__(self, text):
        self.text = text


def _make_provider():
    provider = AnimeWorldProvider()

    async def fake_request(method, path, **kwargs):
        if path.startswith("/play/"):
            return _FakeResponse(_PLAY_HTML)
        if path == "/api/episode/serverPlayerAnimeWorld":
            assert kwargs.get("params", {}).get("id") == "Dinwg"
            return _FakeResponse(_PLAYER_HTML)
        raise AssertionError(f"unexpected request: {method} {path}")

    provider._request = fake_request  # type: ignore[assignment]
    return provider


def test_get_episodes_caches_play_link_id():
    provider = _make_provider()
    eps, total = asyncio.run(provider.get_episodes(321, "hunter-x-hunter-2011.Hsfvk"))
    assert total == 2
    assert [(e.id, e.number) for e in eps] == [(4816, "1"), (4817, "2")]
    # Numeric Episode.id maps to the alphanumeric player link id.
    assert provider._episode_play_ids == {4816: "Dinwg", 4817: "1kOiC"}


def test_resolve_download_url_uses_player_source():
    provider = _make_provider()
    asyncio.run(provider.get_episodes(321, "hunter-x-hunter-2011.Hsfvk"))
    source = asyncio.run(provider.resolve_download_url(4816))
    assert source.type == "direct_mp4"
    assert source.url.endswith("HunterXHunter_Ep_001_SUB_ITA.mp4")
    assert source.headers.get("Referer")


def test_resolve_without_cache_raises():
    provider = _make_provider()
    try:
        asyncio.run(provider.resolve_download_url(4816))
    except RuntimeError as exc:
        assert "Fetch episodes first" in str(exc)
    else:
        raise AssertionError("expected RuntimeError when cache is empty")
