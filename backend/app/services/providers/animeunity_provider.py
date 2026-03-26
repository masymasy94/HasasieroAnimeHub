"""AnimeUnity site provider — consolidates search, anime info, and video extraction."""

from __future__ import annotations

import asyncio
import logging
import re

from ...config import settings
from ...schemas.anime import AnimeDetail, AnimeSearchResult, Episode
from ..animeunity_client import AnimeUnityClient
from .base import SiteProvider, VideoSource

logger = logging.getLogger(__name__)

CSRF_PATTERN = re.compile(r'<meta\s+name="csrf-token"\s+content="([^"]+)"')
MAX_EPISODES_PER_REQUEST = 120

# Extractor patterns
DOWNLOAD_URL_PATTERN = re.compile(r"window\.downloadUrl\s*=\s*['\"](.+?)['\"]")
VIDEO_URL_PATTERN = re.compile(r"url:\s*['\"](.+?)['\"]")
TOKEN_PATTERN = re.compile(r"token':\s*['\"](.+?)['\"]")
EXPIRES_PATTERN = re.compile(r"expires':\s*['\"](.+?)['\"]")


def _extract_episode_title(file_name: str | None) -> str | None:
    if not file_name:
        return None
    name = re.sub(r'\.[a-zA-Z0-9]{2,4}$', '', file_name)
    m = re.search(
        r'S\d+E\d+[.\s](.+?)(?:[.\s](?:\d{3,4}p|WEB|BDRip|DVDRip|HDTV|BluRay|AMZN|NF))',
        name, re.IGNORECASE,
    )
    if m:
        return m.group(1).replace('.', ' ').strip()
    m = re.search(
        r'(?:E|EP|Episode[.\s]?)\d+[.\s](.+?)(?:[.\s](?:\d{3,4}p|WEB|BDRip|DVDRip|HDTV|BluRay|AMZN|NF))',
        name, re.IGNORECASE,
    )
    if m:
        return m.group(1).replace('.', ' ').strip()
    return None


def _parse_genres(raw_genres: list | None) -> list[str]:
    if not raw_genres:
        return []
    genres = []
    for g in raw_genres:
        if isinstance(g, dict):
            genres.append(g.get("name", ""))
        elif isinstance(g, str):
            genres.append(g)
    return genres


class AnimeUnityProvider(SiteProvider):
    def __init__(self) -> None:
        self._client = AnimeUnityClient()
        self._csrf_token: str | None = None

    @property
    def site_id(self) -> str:
        return "animeunity"

    @property
    def site_name(self) -> str:
        return "AnimeUnity"

    # ── Search ──

    async def _get_csrf_token(self) -> str:
        if self._csrf_token:
            return self._csrf_token
        html = await self._client.get_html("/archivio")
        match = CSRF_PATTERN.search(html)
        if match:
            self._csrf_token = match.group(1)
            return self._csrf_token
        raise RuntimeError("Could not extract CSRF token from archivio page")

    async def _post_archivio(self, data: dict) -> dict | list:
        """POST to /archivio/get-animes with automatic CSRF token refresh on 419."""
        csrf = await self._get_csrf_token()
        try:
            return await self._client.post_json(
                "/archivio/get-animes",
                data=data,
                headers={"X-CSRF-TOKEN": csrf, "X-Requested-With": "XMLHttpRequest"},
            )
        except Exception as exc:
            if "419" in str(exc):
                logger.info("CSRF token expired, refreshing session...")
                self._csrf_token = None
                await self._client.close()
                self._client = AnimeUnityClient()
                csrf = await self._get_csrf_token()
                return await self._client.post_json(
                    "/archivio/get-animes",
                    data=data,
                    headers={"X-CSRF-TOKEN": csrf, "X-Requested-With": "XMLHttpRequest"},
                )
            raise

    async def search(self, title: str) -> list[AnimeSearchResult]:
        all_results: dict[int, AnimeSearchResult] = {}

        # Fetch SUB and DUB results in parallel
        data, data_dub = await asyncio.gather(
            self._post_archivio({"title": title, "offset": 0}),
            self._post_archivio({"title": title, "offset": 0, "dubbed": True}),
        )

        for item in self._extract_records(data):
            all_results[item.id] = item
        for item in self._extract_records(data_dub):
            all_results[item.id] = item

        return list(all_results.values())

    async def get_latest(self) -> list[AnimeSearchResult]:
        data = await self._post_archivio({
            "title": "",
            "offset": 0,
            "status": "In Corso",
            "order": "Ultime aggiunte",
        })
        return self._extract_records(data)

    def _extract_records(self, data: dict | list) -> list[AnimeSearchResult]:
        if isinstance(data, dict):
            items = data.get("records", data.get("data", []))
        else:
            items = data

        results = []
        for item in items:
            results.append(
                AnimeSearchResult(
                    id=item["id"],
                    slug=item.get("slug") or "",
                    title=item.get("title") or item.get("title_eng") or "Senza titolo",
                    title_eng=item.get("title_eng"),
                    cover_url=item.get("imageurl"),
                    type=item.get("type"),
                    year=item.get("date"),
                    episodes_count=item.get("real_episodes_count") or item.get("episodes_count"),
                    genres=_parse_genres(item.get("genres")),
                    dub=bool(item.get("dub", False)),
                )
            )
        return results

    # ── Anime Info ──

    async def get_anime_info(self, anime_id: int, slug: str) -> AnimeDetail:
        data = await self._client.get_json(f"/info_api/{anime_id}-{slug}")
        return AnimeDetail(
            id=data.get("id", anime_id),
            slug=data.get("slug") or slug,
            title=data.get("title") or data.get("title_eng") or "Senza titolo",
            title_eng=data.get("title_eng"),
            cover_url=data.get("imageurl"),
            banner_url=data.get("imageurl_cover"),
            plot=data.get("plot"),
            type=data.get("type"),
            year=data.get("date"),
            episodes_count=data.get("episodes_count"),
            genres=_parse_genres(data.get("genres")),
            status=data.get("status"),
            dub=bool(data.get("dub", False)),
            source_site="animeunity",
        )

    async def get_episodes(
        self, anime_id: int, slug: str, start: int = 1, end: int | None = None
    ) -> tuple[list[Episode], int]:
        info = await self._client.get_json(f"/info_api/{anime_id}-{slug}")
        total = info.get("episodes_count", 0)

        if end is None:
            end = total
        if start <= 0:
            start = 1

        episodes: list[Episode] = []
        current_start = start

        while current_start <= end:
            batch_end = min(current_start + MAX_EPISODES_PER_REQUEST - 1, end)
            data = await self._client.get_json(
                f"/info_api/{anime_id}-{slug}/0",
                params={"start_range": current_start, "end_range": batch_end},
            )
            ep_list = data.get("episodes", []) if isinstance(data, dict) else data
            for ep in ep_list:
                episodes.append(
                    Episode(
                        id=ep["id"],
                        number=str(ep.get("number", "")),
                        title=_extract_episode_title(ep.get("file_name")),
                        created_at=ep.get("created_at"),
                        views=ep.get("visite"),
                    )
                )
            current_start = batch_end + 1

        return episodes, total

    # ── Video URL Extraction ──

    async def resolve_download_url(self, episode_id: int) -> VideoSource:
        from ...utils.retry import retry as retry_decorator

        @retry_decorator(max_attempts=3, retryable=(Exception,))
        async def _resolve() -> VideoSource:
            embed_url = await self._client.get_text(f"/embed-url/{episode_id}")
            if not embed_url or not embed_url.startswith("http"):
                raise ExtractionError(f"Invalid embed URL for episode {episode_id}: {embed_url}")

            session = await self._client._ensure_session()
            response = await session.get(embed_url, headers={"Referer": self._client._base_url})
            embed_html = response.text

            mp4_match = DOWNLOAD_URL_PATTERN.search(embed_html)
            if mp4_match:
                return VideoSource(
                    url=mp4_match.group(1),
                    type="direct_mp4",
                    headers={"Referer": embed_url},
                )

            url_match = VIDEO_URL_PATTERN.search(embed_html)
            token_match = TOKEN_PATTERN.search(embed_html)
            expires_match = EXPIRES_PATTERN.search(embed_html)

            if url_match and token_match and expires_match:
                playlist_url = (
                    f"{url_match.group(1)}"
                    f"?token={token_match.group(1)}"
                    f"&referer="
                    f"&expires={expires_match.group(1)}"
                    f"&h=1"
                )
                return VideoSource(
                    url=playlist_url,
                    type="m3u8",
                    headers={"Referer": embed_url},
                )

            raise ExtractionError(f"Could not extract video URL for episode {episode_id}")

        return await _resolve()

    async def get_http_session(self):
        return await self._client._ensure_session()

    async def close(self) -> None:
        await self._client.close()


class ExtractionError(Exception):
    pass
