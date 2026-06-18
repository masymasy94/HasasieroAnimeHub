"""AnimeClick episode-title enrichment.

Streaming providers (AnimeUnity/AnimeWorld/AnimeSaturn) often ship junk or
missing episode titles (e.g. "1080p CR"). AnimeClick has complete, community
curated Italian episode titles, which match the rest of the user's library.

AnimeClick uses a SINGLE entry per show with **continuous** episode numbering
across seasons (e.g. season 2 episode 1 is listed as Ep. 13), plus interspersed
specials (Ep. 12.5). Streaming sources, on the other hand, restart numbering for
each season (a "2nd season" entry is episodes 1..N). To bridge the two we detect
an integer *offset* by anchoring on episodes whose source title already matches
an AnimeClick title, then shift the whole season by that offset.

Everything here is best-effort: any failure falls back to the original title and
never blocks a download.
"""
from __future__ import annotations

import html as _html
import logging
import re
import time
import unicodedata
from collections import Counter
from urllib.parse import quote

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_CACHE_TTL = 24 * 3600  # seconds

# Episode rows: a number cell (Ep.&nbsp;13 / Ep.&nbsp;12.5) followed by the
# title anchor in the next <td>.
_ROW_RE = re.compile(
    r'Ep\.\&nbsp;\s*([\d.]+).*?<td>\s*<a href="/episodio/\d+/[^"]*">\s*(.*?)\s*</a>',
    re.S,
)
_ANIME_LINK_RE = re.compile(r"/anime/(\d+)/([a-z0-9-]+)")

# Source titles we must NOT trust as anchors (release tags, placeholders, …).
_JUNK_RE = re.compile(
    r"(1080p|720p|480p|2160p|\bcr\b|sub\s*ita|\bita\b|\bdub\b|web-?dl|blu-?ray|"
    r"x26[45]|hevc|\.mp4|\.mkv|^\s*episodio?\s*\d+\s*$|^\s*ep\.?\s*\d+\s*$)",
    re.I,
)

# Trailing season markers to strip before searching AnimeClick (its search
# returns nothing for "... 2"). Order matters: explicit words first.
_SEASON_SUFFIX_RE = [
    re.compile(
        r"^(.*?)[\s:_-]+\d+(?:nd|rd|st|th)?\s*"
        r"(?:season|stagione|cour|part(?:e)?|series)\b.*$",
        re.I,
    ),
    re.compile(r"^(.*?)\s+(?:season|stagione)\s+\d+\s*$", re.I),
    re.compile(r"^(.*?)\s+(\d+)\s*$"),  # bare trailing number, e.g. "… Wistoria 2"
]


def _norm(s: str | None) -> str:
    """Accent/case/punctuation-insensitive normalisation for title matching."""
    if not s:
        return ""
    s = _html.unescape(s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s.lower())
    return s.strip()


def _is_meaningful(title: str | None) -> bool:
    if not title:
        return False
    t = title.strip()
    if len(t) < 3 or _JUNK_RE.search(t):
        return False
    return not re.fullmatch(r"[\d\W]+", t)


def strip_season_suffix(title: str) -> str:
    """Return the base show title without a trailing season marker."""
    for rx in _SEASON_SUFFIX_RE:
        m = rx.match(title)
        if m and m.group(1).strip(" :-_"):
            return m.group(1).strip(" :-_")
    return title.strip()


def parse_episodes(html: str) -> list[tuple[str, str]]:
    """Parse an AnimeClick /episodi page into [(number, italian_title), …]."""
    out: list[tuple[str, str]] = []
    for num, title in _ROW_RE.findall(html):
        clean = _html.unescape(title).strip()
        if clean:
            out.append((num, clean))
    return out


def detect_offset(
    source_eps: list[tuple[int, str | None]],
    ac_eps: list[tuple[str, str]],
) -> int | None:
    """Find the integer offset mapping source numbers to AnimeClick numbers.

    Votes are gathered from episodes whose (meaningful) source title matches an
    AnimeClick title; the most common ``ac_number - source_number`` wins. Returns
    ``None`` when there is no confident anchor.
    """
    ac_by_norm: dict[str, list[int]] = {}
    for num, title in ac_eps:
        try:
            f = float(num)
        except ValueError:
            continue
        if f != int(f):  # skip specials like 12.5 as anchors
            continue
        ac_by_norm.setdefault(_norm(title), []).append(int(f))

    votes: Counter[int] = Counter()
    for snum, stitle in source_eps:
        if not _is_meaningful(stitle):
            continue
        for acnum in ac_by_norm.get(_norm(stitle), []):
            votes[acnum - snum] += 1

    if not votes:
        return None
    return votes.most_common(1)[0][0]


def build_title_map(
    source_eps: list[tuple[int, str | None]],
    ac_eps: list[tuple[str, str]],
    *,
    is_sequel: bool,
) -> dict[int, str]:
    """Map source episode number -> AnimeClick Italian title."""
    offset = detect_offset(source_eps, ac_eps)
    if offset is None:
        if is_sequel:
            # Can't anchor a continuation safely -> leave titles untouched.
            return {}
        offset = 0  # season 1 / single cour: AnimeClick numbering aligns 1:1

    ac_int: dict[int, str] = {}
    for num, title in ac_eps:
        try:
            f = float(num)
        except ValueError:
            continue
        if f == int(f):
            ac_int[int(f)] = title

    result: dict[int, str] = {}
    for snum, _ in source_eps:
        title = ac_int.get(snum + offset)
        if title:
            result[snum] = title
    return result


class AnimeClickService:
    """Resolves Italian episode titles from AnimeClick (best-effort, cached)."""

    def __init__(self, provider_registry, base_url: str):
        self._registry = provider_registry
        self._base = base_url.rstrip("/")
        self._session = None
        self._cache: dict[str, tuple[float, dict[int, str]]] = {}

    async def _get(self, path: str) -> str | None:
        try:
            from curl_cffi.requests import AsyncSession

            if self._session is None:
                self._session = AsyncSession(impersonate="chrome", timeout=20)
            resp = await self._session.get(
                f"{self._base}{path}", headers={"User-Agent": _UA}
            )
            if resp.status_code != 200:
                return None
            return resp.text
        except Exception as exc:  # network/parse — never fatal
            logger.warning("AnimeClick request failed for %s: %s", path, exc)
            return None

    async def _find_entry(self, anime_title: str) -> tuple[str, str] | None:
        queries: list[str] = [anime_title]
        base = strip_season_suffix(anime_title)
        if base and base != anime_title:
            queries.append(base)
        seen: set[str] = set()
        for q in queries:
            if q in seen:
                continue
            seen.add(q)
            html = await self._get(f"/cerca/{quote(q)}")
            if not html:
                continue
            for aid, slug in _ANIME_LINK_RE.findall(html):
                return aid, slug
        return None

    async def _source_episodes(
        self, source_site: str, anime_id: int, anime_slug: str
    ) -> list[tuple[int, str | None]]:
        provider = self._registry.get(source_site)
        episodes, _ = await provider.get_episodes(anime_id, anime_slug)
        out: list[tuple[int, str | None]] = []
        for ep in episodes:
            try:
                out.append((int(float(ep.number)), ep.title))
            except (ValueError, TypeError):
                continue
        return out

    async def get_title_map(
        self,
        *,
        anime_title: str,
        anime_slug: str,
        anime_id: int,
        source_site: str,
    ) -> dict[int, str]:
        """Return {source_episode_number: italian_title}; {} on any miss."""
        key = f"{source_site}:{anime_id}:{anime_slug}"
        cached = self._cache.get(key)
        now = time.monotonic()
        if cached and now - cached[0] < _CACHE_TTL:
            return cached[1]

        title_map: dict[int, str] = {}
        try:
            entry = await self._find_entry(anime_title)
            if entry:
                aid, slug = entry
                html = await self._get(f"/anime/{aid}/{slug}/episodi")
                if html:
                    ac_eps = parse_episodes(html)
                    src_eps = await self._source_episodes(
                        source_site, anime_id, anime_slug
                    )
                    is_sequel = strip_season_suffix(anime_title) != anime_title.strip()
                    title_map = build_title_map(
                        src_eps, ac_eps, is_sequel=is_sequel
                    )
                    logger.info(
                        "AnimeClick: matched '%s' -> /anime/%s (%d titles)",
                        anime_title, aid, len(title_map),
                    )
        except Exception as exc:
            logger.warning("AnimeClick enrichment failed for '%s': %s", anime_title, exc)
            title_map = {}

        self._cache[key] = (now, title_map)
        return title_map

    async def resolve_title(
        self,
        *,
        anime_title: str,
        anime_slug: str,
        anime_id: int,
        source_site: str,
        episode_number: str,
        fallback: str | None,
    ) -> str | None:
        """Italian title for one episode, or ``fallback`` if unavailable."""
        try:
            ep_int = int(float(episode_number))
        except (ValueError, TypeError):
            return fallback
        title_map = await self.get_title_map(
            anime_title=anime_title,
            anime_slug=anime_slug,
            anime_id=anime_id,
            source_site=source_site,
        )
        return title_map.get(ep_int, fallback)

    async def close(self) -> None:
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None
