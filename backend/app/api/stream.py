"""Streaming proxy — M3U8 manifest rewriting + segment proxying."""

import json
import logging
import re
from urllib.parse import urlencode, urljoin, quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from .deps import get_provider_registry
from ..services.providers import ProviderRegistry

logger = logging.getLogger(__name__)

router = APIRouter()


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
    import httpx
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        resp = await client.get(url, headers=upstream_headers)
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

    import httpx

    client = httpx.AsyncClient(follow_redirects=True, timeout=120)

    # Forward Range header for MP4 seeking
    range_header = request.headers.get("range")
    if range_header:
        upstream_headers["Range"] = range_header

    resp = await client.send(
        client.build_request("GET", url, headers=upstream_headers),
        stream=True,
    )

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

    async def stream_content():
        try:
            async for chunk in resp.aiter_bytes(chunk_size=65536):
                yield chunk
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
