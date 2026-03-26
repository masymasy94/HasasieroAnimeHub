import asyncio
import json
import logging
import time

from fastapi import APIRouter, Depends, Query
from starlette.responses import StreamingResponse

from ..schemas.anime import AnimeSearchResult, SearchResponse
from ..services.providers import ProviderRegistry
from .deps import get_provider_registry

logger = logging.getLogger(__name__)

router = APIRouter()

PROVIDER_TIMEOUT = 8  # seconds – skip slow providers instead of blocking everything

# In-memory cache for /latest (avoids hitting providers on every page load)
_latest_cache: list[AnimeSearchResult] | None = None
_latest_cache_ts: float = 0.0
_LATEST_CACHE_TTL = 600  # 10 minutes


def _sse_event(event: str, data: dict | list) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/search")
async def search_anime(
    title: str = Query(..., min_length=1),
    registry: ProviderRegistry = Depends(get_provider_registry),
):
    """Stream search results via SSE as each provider responds."""

    async def event_stream():
        providers = registry.all_providers()

        async def _search_one(provider):
            try:
                results = await asyncio.wait_for(
                    provider.search(title), timeout=PROVIDER_TIMEOUT
                )
                for r in results:
                    r.source_site = provider.site_id
                return provider.site_id, results
            except asyncio.TimeoutError:
                logger.warning("Search timed out for %s (>%ss)", provider.site_id, PROVIDER_TIMEOUT)
                return provider.site_id, []
            except Exception as exc:
                logger.warning("Search failed for %s: %s", provider.site_id, exc)
                return provider.site_id, []

        tasks = [asyncio.create_task(_search_one(p)) for p in providers]

        for coro in asyncio.as_completed(tasks):
            site_id, results = await coro
            yield _sse_event("results", {
                "source_site": site_id,
                "results": [r.model_dump() for r in results],
            })

        yield _sse_event("done", {})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/latest", response_model=SearchResponse)
async def latest_anime(
    registry: ProviderRegistry = Depends(get_provider_registry),
):
    """Get latest from all providers in parallel, with in-memory cache."""
    global _latest_cache, _latest_cache_ts

    now = time.monotonic()
    if _latest_cache is not None and (now - _latest_cache_ts) < _LATEST_CACHE_TTL:
        return SearchResponse(results=_latest_cache)

    providers = registry.all_providers()

    async def _latest_one(provider):
        try:
            results = await asyncio.wait_for(
                provider.get_latest(), timeout=PROVIDER_TIMEOUT
            )
            for r in results:
                r.source_site = provider.site_id
            return results
        except asyncio.TimeoutError:
            logger.warning("Latest timed out for %s (>%ss)", provider.site_id, PROVIDER_TIMEOUT)
            return []
        except Exception as exc:
            logger.warning("Latest failed for %s: %s", provider.site_id, exc)
            return []

    all_results = await asyncio.gather(*[_latest_one(p) for p in providers])

    merged = []
    for results in all_results:
        merged.extend(results)

    _latest_cache = merged
    _latest_cache_ts = now

    return SearchResponse(results=merged)
