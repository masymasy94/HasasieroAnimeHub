"""AnimeSaturn site provider — animesaturn.cx scraping.

- Search via JSON API: /index.php?search=1&key=
- Anime page: /anime/{slug}
- Episodes: a.bottone-ep on anime page
- Video: episode page → watch page → <source> tag or JS file: "..." regex
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from ...schemas.anime import AnimeDetail, AnimeSearchResult, Episode
from .base import SiteProvider, VideoSource

logger = logging.getLogger(__name__)

BASE_URL = "https://www.animesaturn.cx"

# Regex to extract video URL from inline JS: file: "https://...mp4" or .m3u8
VIDEO_FILE_PATTERN = re.compile(r'file:\s*"(https?://[^"]+\.(mp4|m3u8)[^"]*)"')


class AnimeSaturnProvider(SiteProvider):
    def __init__(self) -> None:
        self._session: AsyncSession | None = None

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

    @property
    def site_id(self) -> str:
        return "animesaturn"

    @property
    def site_name(self) -> str:
        return "AnimeSaturn"

    # ── Search ──

    async def search(self, title: str) -> list[AnimeSearchResult]:
        session = await self._ensure_session()
        response = await session.get(
            f"{BASE_URL}/index.php",
            params={"search": "1", "key": title},
        )
        data = response.json()

        results = []
        for item in data if isinstance(data, list) else []:
            link = item.get("link", "")
            name = item.get("name", "Senza titolo")
            image = item.get("image", "")

            anime_id = abs(hash(link)) % 10_000_000

            # Infer type from title
            anime_type = "TV"
            name_lower = name.lower()
            for t in ("Movie", "OVA", "ONA", "Special"):
                if t.lower() in name_lower:
                    anime_type = t
                    break

            # Extract year from release date (e.g. "20 Ottobre 1999")
            year = None
            release = item.get("release", "")
            year_match = re.search(r"(\d{4})", release)
            if year_match:
                year = year_match.group(1)

            # Detect dub from title
            dub = "(ita)" in name_lower

            results.append(
                AnimeSearchResult(
                    id=anime_id,
                    slug=link,
                    title=name,
                    cover_url=image or None,
                    type=anime_type,
                    year=year,
                    dub=dub,
                    source_site="animesaturn",
                )
            )
        return results

    async def get_latest(self) -> list[AnimeSearchResult]:
        session = await self._ensure_session()
        response = await session.get(BASE_URL)
        return self._parse_card_list(response.text)

    def _parse_card_list(self, html: str) -> list[AnimeSearchResult]:
        soup = BeautifulSoup(html, "html.parser")
        results = []

        for card in soup.select(".anime-card-newanime, .item-archivio"):
            link_el = card.select_one("a[href]")
            if not link_el:
                continue

            href = link_el.get("href", "")
            slug_match = re.search(r"/anime/(.+?)(?:/|$)", href)
            slug = slug_match.group(1) if slug_match else ""
            if not slug:
                continue

            img = card.select_one("img")
            cover_url = img.get("src") if img else None
            title_el = card.select_one(".info-archivio h3 a, a.name, .title")
            title_text = title_el.get_text(strip=True) if title_el else link_el.get_text(strip=True)

            anime_id = abs(hash(slug)) % 10_000_000

            results.append(
                AnimeSearchResult(
                    id=anime_id,
                    slug=slug,
                    title=title_text,
                    cover_url=cover_url,
                    source_site="animesaturn",
                )
            )
        return results

    # ── Anime Info ──

    async def get_anime_info(self, anime_id: int, slug: str) -> AnimeDetail:
        session = await self._ensure_session()
        response = await session.get(f"{BASE_URL}/anime/{slug}")
        soup = BeautifulSoup(response.text, "html.parser")

        # Title
        title_el = soup.select_one(".container.anime-title-as b, h1.title")
        title = title_el.get_text(strip=True) if title_el else slug

        # Cover
        cover_el = soup.select_one("img.img-fluid.cover-anime, img.cover-anime")
        cover_url = cover_el.get("src") if cover_el else None

        # Plot
        plot_el = soup.select_one("#full-trama, #trama")
        plot = plot_el.get_text(strip=True) if plot_el else None

        # Info box
        info_box = soup.select_one(".container.shadow.rounded.bg-dark-as-box.p-3, .info-box")
        info_text = info_box.get_text() if info_box else ""

        # Genres
        genres = [
            badge.get_text(strip=True)
            for badge in soup.select(".badge.badge-light.generi-as, a.badge")
        ]

        # Year
        year = None
        year_match = re.search(r"Data di uscita:\s*(.+?)(?:\n|$)", info_text)
        if year_match:
            year = year_match.group(1).strip()

        # Status
        status = None
        status_match = re.search(r"Stato:\s*(.+?)(?:\n|$)", info_text)
        if status_match:
            status = status_match.group(1).strip()

        # Episodes count
        episodes_count = None
        ep_match = re.search(r"Episodi:\s*(\d+)", info_text)
        if ep_match:
            episodes_count = int(ep_match.group(1))

        # Type (TV, Movie, OVA, Special)
        anime_type = "TV"
        type_badge = soup.select_one("span.badge.badge-secondary")
        if type_badge:
            badge_text = type_badge.get_text(strip=True)
            for t in ("Movie", "OVA", "ONA", "Special"):
                if t.lower() in badge_text.lower():
                    anime_type = t
                    break

        return AnimeDetail(
            id=anime_id,
            slug=slug,
            title=title,
            cover_url=cover_url,
            plot=plot,
            type=anime_type,
            year=year,
            episodes_count=episodes_count,
            genres=genres,
            status=status,
            source_site="animesaturn",
        )

    # ── Episodes ──

    async def get_episodes(
        self, anime_id: int, slug: str, start: int = 1, end: int | None = None
    ) -> tuple[list[Episode], int]:
        session = await self._ensure_session()
        response = await session.get(f"{BASE_URL}/anime/{slug}")
        soup = BeautifulSoup(response.text, "html.parser")

        episodes = []
        for ep_el in soup.select("a.bottone-ep"):
            href = ep_el.get("href", "")
            # Extract episode number from href: /ep/Anime-Name-ep-3
            ep_match = re.search(r"-ep-(\d+)", href)
            ep_num = ep_match.group(1) if ep_match else ep_el.get_text(strip=True)

            # Use a stable ID from the episode URL
            ep_id = abs(hash(href)) % 10_000_000

            episodes.append(
                Episode(
                    id=ep_id,
                    number=str(ep_num),
                )
            )

        # Store episode URLs for resolve_download_url
        self._episode_urls: dict[int, str] = {}
        for ep_el in soup.select("a.bottone-ep"):
            href = ep_el.get("href", "")
            ep_id = abs(hash(href)) % 10_000_000
            self._episode_urls[ep_id] = href

        total = len(episodes)
        if end is None:
            end = total
        if start <= 0:
            start = 1

        filtered = []
        for ep in episodes:
            try:
                num = int(float(ep.number))
                if start <= num <= end:
                    filtered.append(ep)
            except (ValueError, TypeError):
                filtered.append(ep)

        return filtered, total

    # ── Video URL Resolution ──

    async def resolve_download_url(self, episode_id: int) -> VideoSource:
        session = await self._ensure_session()

        ep_url = getattr(self, "_episode_urls", {}).get(episode_id)
        if not ep_url:
            raise RuntimeError(f"No cached URL for AnimeSaturn episode {episode_id}. Fetch episodes first.")

        # Step 1: Fetch episode page to get the watch page link
        response = await session.get(ep_url)
        soup = BeautifulSoup(response.text, "html.parser")

        watch_url = None
        # Look for the watch link — typically a[href] containing /watch?
        for a_tag in soup.select("a[href]"):
            href = a_tag.get("href", "")
            if "/watch?" in href:
                watch_url = href
                break

        if not watch_url:
            # Fallback: look for the main content link
            link_el = soup.select_one("div.card-body a[href], a.btn.btn-light")
            if link_el:
                watch_url = link_el.get("href", "")

        if not watch_url:
            raise RuntimeError(f"Could not find watch URL on AnimeSaturn episode page: {ep_url}")

        # Step 2: Fetch watch page to extract video source
        response = await session.get(watch_url)
        watch_html = response.text
        watch_soup = BeautifulSoup(watch_html, "html.parser")

        # Method A: <source> tag with direct URL
        source_el = watch_soup.select_one("video source[src], source[src]")
        if source_el:
            src = source_el.get("src", "")
            if src:
                video_type = "m3u8" if ".m3u8" in src else "direct_mp4"
                return VideoSource(
                    url=src,
                    type=video_type,
                    headers={"Referer": BASE_URL},
                )

        # Method B: JS file: "..." pattern
        match = VIDEO_FILE_PATTERN.search(watch_html)
        if match:
            url = match.group(1)
            video_type = "m3u8" if ".m3u8" in url else "direct_mp4"
            return VideoSource(
                url=url,
                type=video_type,
                headers={"Referer": BASE_URL},
            )

        # Method C: Try with &s=alt parameter for alternative server
        if "?" in watch_url and "&s=alt" not in watch_url:
            alt_url = watch_url + "&s=alt"
            response = await session.get(alt_url)
            alt_html = response.text
            alt_soup = BeautifulSoup(alt_html, "html.parser")

            source_el = alt_soup.select_one("video source[src], source[src]")
            if source_el:
                src = source_el.get("src", "")
                if src:
                    video_type = "m3u8" if ".m3u8" in src else "direct_mp4"
                    return VideoSource(
                        url=src,
                        type=video_type,
                        headers={"Referer": BASE_URL},
                    )

            match = VIDEO_FILE_PATTERN.search(alt_html)
            if match:
                url = match.group(1)
                video_type = "m3u8" if ".m3u8" in url else "direct_mp4"
                return VideoSource(
                    url=url,
                    type=video_type,
                    headers={"Referer": BASE_URL},
                )

        raise RuntimeError(f"Could not resolve video URL for AnimeSaturn episode {episode_id}")

    async def get_http_session(self):
        return await self._ensure_session()

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None
