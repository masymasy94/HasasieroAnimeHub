"""Streaming proxy — M3U8 manifest rewriting + segment proxying."""

import asyncio
import json
import logging
import re
from urllib.parse import urlencode, urljoin, quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from .deps import get_provider_registry
from ..services.providers import ProviderRegistry

logger = logging.getLogger(__name__)

router = APIRouter()

RETRY_ATTEMPTS = 3
# CDN edges answer 503 "temporarily unavailable" on a signed URL that returns 206
# seconds later — retry those like a transport error so a seek landing during one
# blip doesn't surface as a hard, playback-killing error.
RETRYABLE_STATUS = frozenset({502, 503, 504})
# A seek far ahead lands on a byte range the edge hasn't warmed from origin yet; it
# answers 503 for *tens of seconds* (observed ~35s across edges, even on a fresh
# token) until that range is ready. A ~1.5s budget gives up mid-warmup and kills
# playback, so bridge the whole window with capped backoff.
SEND_RETRY_MAX_SECONDS = 40.0


async def _send_with_retry(
    client: httpx.AsyncClient, request: httpx.Request, stream: bool = False
) -> httpx.Response:
    """Send a request, retrying transient failures: transport errors and 5xx blips.

    CDN edges go unreachable for a minute at a time (blip, ISP-level block) and also
    answer transient 503s on the same signed URL; without this a single failed connect
    or a 503 during a seek kills playback mid-episode. Retries for up to
    SEND_RETRY_MAX_SECONDS with capped exponential backoff so a far seek becomes a
    buffering pause, not a dead player: the browser holds the range request open the
    whole time and resumes on its own once the edge finally serves the 206.
    """
    # ponytail: capped-backoff time budget (0.5,1,2,4,8,8,… up to ~40s). Bridges an
    # edge warming a cold byte range; still bounded so a genuine outage fails cleanly.
    delay, waited = 0.5, 0.0
    while True:
        over_budget = waited >= SEND_RETRY_MAX_SECONDS
        try:
            resp = await client.send(request, stream=stream)
        except httpx.TransportError as exc:
            if over_budget:
                raise
            logger.warning("upstream %s failed (%s), retry in %.1fs", request.url.host, exc, delay)
        else:
            if resp.status_code not in RETRYABLE_STATUS or over_budget:
                return resp
            await resp.aclose()
            logger.warning("upstream %s returned %d, retry in %.1fs", request.url.host, resp.status_code, delay)
        await asyncio.sleep(delay)
        waited += delay
        delay = min(delay * 2, 8.0)


@router.get("/stream/source/{episode_id}")
async def get_stream_source(
    episode_id: int,
    site: str = "animeunity",
    registry: ProviderRegistry = Depends(get_provider_registry),
):
    """Resolve an episode to a streamable URL. Returns the proxy URL ready for hls.js."""
    provider = registry.get(site)
    source = await provider.resolve_download_url(episode_id)

    if source.type == "m3u8":
        # Return a proxied M3U8 URL
        headers_json = json.dumps(source.headers or {})
        proxy_url = f"/api/proxy/m3u8?url={quote(source.url)}&headers={quote(headers_json)}"
        return {"url": proxy_url, "type": "m3u8"}
    else:
        # Direct MP4 — proxy through segment endpoint
        headers_json = json.dumps(source.headers or {})
        proxy_url = f"/api/proxy/segment?url={quote(source.url)}&headers={quote(headers_json)}"
        return {"url": proxy_url, "type": "mp4"}


@router.get("/proxy/m3u8")
async def proxy_m3u8(
    request: Request,
    url: str = Query(...),
    headers: str = Query("{}"),
):
    """Fetch an M3U8 manifest and rewrite segment/playlist URLs to route through the proxy."""
    try:
        upstream_headers = json.loads(headers)
    except json.JSONDecodeError:
        upstream_headers = {}

    # Use httpx for the upstream request
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        try:
            resp = await _send_with_retry(client, client.build_request("GET", url, headers=upstream_headers))
        except httpx.TransportError as exc:
            raise HTTPException(status_code=502, detail="Upstream unreachable") from exc
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Upstream M3U8 fetch failed")
        manifest = resp.text

    base_url = url.rsplit("/", 1)[0] + "/"
    rewritten = _rewrite_m3u8(manifest, base_url, headers)

    return StreamingResponse(
        iter([rewritten.encode()]),
        media_type="application/vnd.apple.mpegurl",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-cache",
        },
    )


@router.get("/proxy/segment")
async def proxy_segment(
    request: Request,
    url: str = Query(...),
    headers: str = Query("{}"),
):
    """Proxy a video segment (.ts, .mp4, etc.) with streaming."""
    try:
        upstream_headers = json.loads(headers)
    except json.JSONDecodeError:
        upstream_headers = {}

    client = httpx.AsyncClient(follow_redirects=True, timeout=120)

    # Forward Range header for MP4 seeking
    range_header = request.headers.get("range")
    if range_header:
        upstream_headers["Range"] = range_header

    try:
        resp = await _send_with_retry(
            client,
            client.build_request("GET", url, headers=upstream_headers),
            stream=True,
        )
    except httpx.TransportError as exc:
        await client.aclose()
        logger.warning("segment proxy: upstream unreachable — %s", exc)
        raise HTTPException(status_code=502, detail="Upstream unreachable") from exc

    if resp.status_code not in (200, 206):
        await resp.aclose()
        await client.aclose()
        raise HTTPException(status_code=resp.status_code, detail="Upstream segment fetch failed")

    # Determine content type
    content_type = resp.headers.get("content-type", "video/mp2t")
    if url.endswith(".mp4") or "mp4" in content_type:
        content_type = "video/mp4"
    elif url.endswith(".ts"):
        content_type = "video/mp2t"

    response_headers = {
        "Access-Control-Allow-Origin": "*",
        "Content-Type": content_type,
    }

    # Forward content-length and content-range for seeking
    if "content-length" in resp.headers:
        response_headers["Content-Length"] = resp.headers["content-length"]
    if "content-range" in resp.headers:
        response_headers["Content-Range"] = resp.headers["content-range"]
    if "accept-ranges" in resp.headers:
        response_headers["Accept-Ranges"] = resp.headers["accept-ranges"]

    # Original client Range (bytes=X-Y or bytes=X-), so resumes can be computed as
    # an absolute offset and stay within whatever upper bound the client asked for.
    # A Range we don't recognize (e.g. a suffix range "bytes=-500") means we can't
    # safely compute a resume offset — better to not resume than to guess wrong.
    range_match = re.match(r"bytes=(\d+)-(\d*)", range_header) if range_header else None
    can_resume = range_match is not None if range_header else True
    orig_start = int(range_match.group(1)) if range_match else 0
    orig_end = int(range_match.group(2)) if range_match and range_match.group(2) else None

    async def stream_content():
        nonlocal resp, client
        sent = 0
        resumes = 0
        try:
            while True:
                try:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        sent += len(chunk)
                        yield chunk
                    return
                # Any transport-level break mid-body, not just a clean "peer closed"
                # (RemoteProtocolError): a reset connection surfaces as ReadError and a
                # stalled edge as ReadTimeout, and both used to escape as a 500 that
                # froze the picture for good.
                except httpx.TransportError as exc:
                    if not can_resume:
                        raise
                    resumes += 1
                    if resumes > RETRY_ATTEMPTS:
                        logger.warning("segment proxy: giving up after %d resumes on %s (%s)", RETRY_ATTEMPTS, url, exc)
                        return
                    resume_start = orig_start + sent
                    resume_headers = dict(upstream_headers)
                    resume_headers["Range"] = (
                        f"bytes={resume_start}-{orig_end}" if orig_end is not None else f"bytes={resume_start}-"
                    )
                    logger.warning("segment proxy: upstream dropped at byte %d, resuming (%s)", resume_start, exc)
                    await resp.aclose()
                    await client.aclose()
                    client = httpx.AsyncClient(follow_redirects=True, timeout=120)
                    try:
                        resp = await _send_with_retry(
                            client, client.build_request("GET", url, headers=resume_headers), stream=True
                        )
                    except httpx.TransportError as retry_exc:
                        logger.warning("segment proxy: resume fetch failed (%s)", retry_exc)
                        return
                    if resp.status_code != 206:
                        logger.warning(
                            "segment proxy: resume got status %d instead of 206, aborting stream",
                            resp.status_code,
                        )
                        await resp.aclose()
                        return
        finally:
            await resp.aclose()
            await client.aclose()

    return StreamingResponse(
        stream_content(),
        status_code=resp.status_code,
        headers=response_headers,
    )


def _rewrite_m3u8(manifest: str, base_url: str, headers_param: str) -> str:
    """Rewrite URLs in an M3U8 manifest to route through our proxy."""
    lines = manifest.strip().split("\n")
    result = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Rewrite #EXT-X-KEY URI
        if stripped.startswith("#EXT-X-KEY"):
            uri_match = re.search(r'URI="([^"]+)"', stripped)
            if uri_match:
                key_url = _resolve_url(uri_match.group(1), base_url)
                proxy_url = f"/api/proxy/segment?url={quote(key_url)}&headers={quote(headers_param)}"
                stripped = stripped.replace(uri_match.group(1), proxy_url)
            result.append(stripped)

        # Rewrite #EXT-X-MAP URI
        elif stripped.startswith("#EXT-X-MAP"):
            uri_match = re.search(r'URI="([^"]+)"', stripped)
            if uri_match:
                map_url = _resolve_url(uri_match.group(1), base_url)
                proxy_url = f"/api/proxy/segment?url={quote(map_url)}&headers={quote(headers_param)}"
                stripped = stripped.replace(uri_match.group(1), proxy_url)
            result.append(stripped)

        # Pass through other tags
        elif stripped.startswith("#"):
            result.append(stripped)

        # Rewrite URL lines (segments or variant playlists)
        elif stripped:
            full_url = _resolve_url(stripped, base_url)
            if full_url.endswith(".m3u8") or "m3u8" in full_url:
                proxy_url = f"/api/proxy/m3u8?url={quote(full_url)}&headers={quote(headers_param)}"
            else:
                proxy_url = f"/api/proxy/segment?url={quote(full_url)}&headers={quote(headers_param)}"
            result.append(proxy_url)
        else:
            result.append(stripped)

    return "\n".join(result) + "\n"


def _resolve_url(url: str, base_url: str) -> str:
    """Resolve a potentially relative URL against a base URL."""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return urljoin(base_url, url)
