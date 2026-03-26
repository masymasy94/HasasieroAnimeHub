"""AnimeWorld site provider — animeworld.ac scraping.

Based on AnimeWorld-API patterns:
- Search via POST /api/search/v2?keyword=
- CSRF token from <meta id="csrf-token">
- Episodes from anime page HTML (li.episode > a)
- Download via POST /api/download/{episode_id} → CDN URL
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from ...schemas.anime import AnimeDetail, AnimeSearchResult, Episode
from .base import SiteProvider, VideoSource

logger = logging.getLogger(__name__)

BASE_URL = "https://www.animeworld.ac"
CSRF_PATTERN = re.compile(r'<meta.*?id="csrf-token"\s*?content="(.*?)"')
SECURITY_COOKIE_PATTERN = re.compile(r"(SecurityAW-\w+)=(.*?)\s*;")


class AnimeWorldProvider(SiteProvider):
    def __init__(self) -> None:
        self._session: AsyncSession | None = None
        self._csrf_token: str | None = None

    async def _ensure_session(self) -> AsyncSession:
        if self._session is None:
            self._session = AsyncSession(
                impersonate="chrome",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Referer": BASE_URL,
                },
                timeout=30,
            )
        return self._session

    async def _get_csrf_token(self) -> str:
        """Fetch CSRF token from homepage, handling SecurityAW cookie if needed."""
        if self._csrf_token:
            return self._csrf_token

        session = await self._ensure_session()
        response = await session.get(f"{BASE_URL}/")

        # Handle SecurityAW cookie challenge (status 202 or JS cookie set)
        text = response.text
        cookie_match = SECURITY_COOKIE_PATTERN.search(text)
        if cookie_match or response.status_code == 202:
            if cookie_match:
                session.cookies.set(cookie_match.group(1), cookie_match.group(2))
            response = await session.get(f"{BASE_URL}/")
            text = response.text

        match = CSRF_PATTERN.search(text)
        if match:
            self._csrf_token = match.group(1)
            return self._csrf_token
        raise RuntimeError("Could not extract CSRF token from AnimeWorld")

    async def _request(self, method: str, path: str, **kwargs):
        """Make a request with CSRF token and security cookie handling."""
        session = await self._ensure_session()
        csrf = await self._get_csrf_token()

        headers = kwargs.pop("headers", {})
        headers["csrf-token"] = csrf

        url = f"{BASE_URL}{path}"
        if method == "GET":
            response = await session.get(url, headers=headers, **kwargs)
        else:
            response = await session.post(url, headers=headers, **kwargs)

        # Re-bootstrap session on auth failure
        if response.status_code in (401, 403):
            self._csrf_token = None
            csrf = await self._get_csrf_token()
            headers["csrf-token"] = csrf
            if method == "GET":
                response = await session.get(url, headers=headers, **kwargs)
            else:
                response = await session.post(url, headers=headers, **kwargs)

        response.raise_for_status()
        return response

    @property
    def site_id(self) -> str:
        return "animeworld"

    @property
    def site_name(self) -> str:
        return "AnimeWorld"

    # ── Search ──

    async def search(self, title: str) -> list[AnimeSearchResult]:
        response = await self._request(
            "POST",
            f"/api/search/v2?keyword={title}",
        )
        data = response.json()
        animes = data.get("animes", [])

        results = []
        for item in animes:
            slug = item.get("link", "")
            identifier = item.get("identifier", "")
            full_slug = f"{slug}.{identifier}" if identifier else slug

            genres = []
            for cat in item.get("categories", []):
                if isinstance(cat, dict):
                    genres.append(cat.get("name", ""))

            ep_count = item.get("episodes")
            try:
                ep_count = int(ep_count) if ep_count is not None else None
            except (ValueError, TypeError):
                ep_count = None

            results.append(
                AnimeSearchResult(
                    id=int(item.get("id", 0)),
                    slug=full_slug,
                    title=item.get("name", "Senza titolo"),
                    title_eng=item.get("jtitle"),
                    cover_url=item.get("image"),
                    type=item.get("type"),
                    year=item.get("year"),
                    episodes_count=ep_count,
                    genres=genres,
                    dub=item.get("dub") == "1" or item.get("language") == "it",
                )
            )
        return results

    async def get_latest(self) -> list[AnimeSearchResult]:
        response = await self._request("GET", "/updated")
        return self._parse_card_list(response.text)

    def _parse_card_list(self, html: str) -> list[AnimeSearchResult]:
        """Parse anime cards from an HTML page (used for latest/updated)."""
        soup = BeautifulSoup(html, "html.parser")
        results = []

        for card in soup.select(".film-list .item, .content .item"):
            link = card.select_one("a.name")
            if not link:
                continue

            href = link.get("href", "")
            # /play/slug.identifier or /play/slug.identifier/
            slug_match = re.search(r"/play/(.+?)(?:/|$)", href)
            slug = slug_match.group(1) if slug_match else ""

            # Stable ID from slug hash
            anime_id = abs(hash(slug)) % 10_000_000

            img = card.select_one("img")
            cover_url = img.get("src") if img else None
            title_text = link.get_text(strip=True)

            results.append(
                AnimeSearchResult(
                    id=anime_id,
                    slug=slug,
                    title=title_text,
                    cover_url=cover_url,
                )
            )
        return results

    # ── Anime Info ──

    async def get_anime_info(self, anime_id: int, slug: str) -> AnimeDetail:
        response = await self._request("GET", f"/play/{slug}")
        soup = BeautifulSoup(response.text, "html.parser")

        title_el = soup.select_one("h1#anime-title, h1.title")
        title = title_el.get_text(strip=True) if title_el else slug
        title_eng = title_el.get("data-jtitle") if title_el else None

        cover_el = soup.select_one("div#thumbnail-watch img, .thumb img")
        cover_url = cover_el.get("src") if cover_el else None

        plot_el = soup.select_one("div.desc")
        plot = plot_el.get_text(strip=True) if plot_el else None

        # Parse info dt/dd pairs
        genres = []
        year = None
        anime_type = None
        status = None
        episodes_count = None

        for row in soup.select("div.info div.row"):
            dt = row.select_one("dt")
            dd = row.select_one("dd")
            if not dt or not dd:
                continue
            key = dt.get_text(strip=True).lower()
            val = dd.get_text(strip=True)
            if "genere" in key:
                genres = [a.get_text(strip=True) for a in dd.select("a")]
            elif "data" in key or "uscita" in key:
                year = val
            elif "categoria" in key or "tipo" in key:
                anime_type = val
            elif "stato" in key:
                status = val
            elif "episodi" in key:
                try:
                    episodes_count = int(val)
                except ValueError:
                    pass

        return AnimeDetail(
            id=anime_id,
            slug=slug,
            title=title,
            title_eng=title_eng,
            cover_url=cover_url,
            plot=plot,
            type=anime_type,
            year=year,
            episodes_count=episodes_count,
            genres=genres,
            status=status,
            source_site="animeworld",
        )

    # ── Episodes ──

    async def get_episodes(
        self, anime_id: int, slug: str, start: int = 1, end: int | None = None
    ) -> tuple[list[Episode], int]:
        response = await self._request("GET", f"/play/{slug}")
        soup = BeautifulSoup(response.text, "html.parser")

        episodes = []
        # Prefer AnimeWorld Server (data-name="9"), fallback to active server, then any
        server_container = (
            soup.select_one('div.server[data-name="9"]')
            or soup.select_one("div.server.active")
            or soup.select_one("div.server")
        )

        if server_container:
            for ep_el in server_container.select("li.episode a"):
                ep_num = ep_el.get("data-episode-num", ep_el.get("data-num", ep_el.get_text(strip=True)))
                ep_id_str = ep_el.get("data-episode-id", ep_el.get("data-id", "0"))
                try:
                    ep_id = int(ep_id_str)
                except ValueError:
                    ep_id = abs(hash(ep_id_str)) % 10_000_000

                episodes.append(
                    Episode(
                        id=ep_id,
                        number=str(ep_num),
                    )
                )

        total = len(episodes)
        if end is None:
            end = total
        if start <= 0:
            start = 1

        # Filter by range (handle non-numeric episode numbers gracefully)
        filtered = []
        for ep in episodes:
            try:
                num = int(float(ep.number))
                if start <= num <= end:
                    filtered.append(ep)
            except (ValueError, TypeError):
                filtered.append(ep)  # Include non-numeric episodes

        return filtered, total

    # ── Video URL Resolution ──

    async def resolve_download_url(self, episode_id: int) -> VideoSource:
        # Method 1: POST /api/download/{id} (preferred, returns CDN URL)
        try:
            response = await self._request("POST", f"/api/download/{episode_id}")
            data = response.json()
            links = data.get("links", {})

            # Try AnimeWorld Server (ID "9") first
            for server_id in ("9", "4", "8"):
                if server_id in links:
                    server_data = links[server_id]
                    for quality_key, quality_data in server_data.items():
                        if quality_key == "server":
                            continue
                        if isinstance(quality_data, dict):
                            url = quality_data.get("alternativeLink") or quality_data.get("link", "")
                            if url:
                                # Strip download-file.php wrapper
                                url = url.replace("download-file.php?id=", "")
                                return VideoSource(
                                    url=url,
                                    type="direct_mp4",
                                    headers={"Referer": BASE_URL},
                                )
        except Exception as exc:
            logger.warning("AnimeWorld /api/download failed: %s, trying fallback", exc)

        # Method 2: GET /api/episode/info (fallback, older API)
        try:
            response = await self._request("GET", f"/api/episode/info", params={"id": str(episode_id)})
            data = response.json()
            grabber = data.get("grabber", "")
            if grabber:
                return VideoSource(
                    url=grabber,
                    type="direct_mp4",
                    headers={"Referer": BASE_URL},
                )
        except Exception as exc:
            logger.warning("AnimeWorld /api/episode/info failed: %s", exc)

        raise RuntimeError(f"Could not resolve download URL for AnimeWorld episode {episode_id}")

    async def get_http_session(self):
        return await self._ensure_session()

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None
