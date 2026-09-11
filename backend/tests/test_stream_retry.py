import asyncio

import httpx
import pytest

from app.api.stream import (
    EDGE_HOSTS,
    RETRY_ATTEMPTS,
    SEND_RETRY_MAX_SECONDS,
    _send_with_retry,
)


class _FlakyClient:
    """Fails `failures` times with a ConnectError, then succeeds."""

    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0

    async def send(self, request, stream=False):
        self.calls += 1
        if self.calls <= self.failures:
            raise httpx.ConnectError("All connection attempts failed")
        return httpx.Response(200, request=request)


class _Resp:
    """Minimal upstream response — real streamed responses get aclose()d before a
    status-retry, so the fake needs an async aclose() too."""

    def __init__(self, status_code: int):
        self.status_code = status_code

    async def aclose(self):
        pass


class _Flaky503Client:
    """Answers 503 `failures` times, then 200 — the transient CDN blip on a seek."""

    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0

    async def send(self, request, stream=False):
        self.calls += 1
        return _Resp(503 if self.calls <= self.failures else 200)


def _request() -> httpx.Request:
    return httpx.Request("GET", "https://cdn.example/1080p.mp4")


@pytest.fixture
def slept(monkeypatch):
    """Run the backoff instantly and collect the delays it asked for — a down upstream
    burns the whole ~40s budget, which is not something to wait for in a test."""
    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("app.api.stream.asyncio.sleep", fake_sleep)
    return delays


def test_recovers_from_transient_connect_error(slept):
    client = _FlakyClient(failures=RETRY_ATTEMPTS - 1)
    resp = asyncio.run(_send_with_retry(client, _request(), stream=True))
    assert resp.status_code == 200
    assert client.calls == RETRY_ATTEMPTS


def test_raises_when_upstream_stays_down(slept):
    client = _FlakyClient(failures=99)
    with pytest.raises(httpx.ConnectError):
        asyncio.run(_send_with_retry(client, _request(), stream=True))
    # Gives up on the time budget, not on an attempt count: a far seek needs the whole
    # window to outlast an edge warming a cold byte range.
    assert sum(slept) >= SEND_RETRY_MAX_SECONDS


def test_recovers_from_transient_503(slept):
    client = _Flaky503Client(failures=RETRY_ATTEMPTS - 1)
    resp = asyncio.run(_send_with_retry(client, _request(), stream=True))
    assert resp.status_code == 200
    assert client.calls == RETRY_ATTEMPTS


def test_returns_final_503_when_upstream_stays_down(slept):
    client = _Flaky503Client(failures=99)
    resp = asyncio.run(_send_with_retry(client, _request(), stream=True))
    assert resp.status_code == 503
    assert sum(slept) >= SEND_RETRY_MAX_SECONDS


class _BlockedEdgeClient:
    """One edge rate-limits us with 503s; every other edge serves the same token."""

    def __init__(self, blocked: str):
        self.blocked = blocked
        self.hosts: list[str] = []

    async def send(self, request, stream=False):
        self.hosts.append(request.url.host)
        return _Resp(503 if request.url.host == self.blocked else 206)


def test_503_moves_to_another_edge(slept):
    client = _BlockedEdgeClient(blocked=EDGE_HOSTS[0])
    request = httpx.Request("GET", f"https://{EDGE_HOSTS[0]}/download/1080p.mp4?token=x")
    resp = asyncio.run(_send_with_retry(client, request, stream=True))
    assert resp.status_code == 206
    # Straight to the next edge, no waiting: the block is per edge host, and a signed
    # vixcloud token is valid on all of them.
    assert client.hosts == [EDGE_HOSTS[0], EDGE_HOSTS[1]]
    assert slept == []


def test_all_edges_blocked_backs_off_once_per_round(slept):
    client = _Flaky503Client(failures=99)
    request = httpx.Request("GET", f"https://{EDGE_HOSTS[0]}/download/1080p.mp4?token=x")
    resp = asyncio.run(_send_with_retry(client, request, stream=True))
    assert resp.status_code == 503
    # One sleep per full lap of the edges, not per attempt.
    assert client.calls >= len(EDGE_HOSTS) * len(slept)
    assert sum(slept) >= SEND_RETRY_MAX_SECONDS


def test_stops_retrying_when_client_is_gone(slept):
    client = _Flaky503Client(failures=99)

    async def gone():
        return True

    resp = asyncio.run(_send_with_retry(client, _request(), stream=True, client_gone=gone))
    # The browser abandoned this range (a seek, a new episode): one attempt, then stop —
    # retrying for a viewer who left is what gets the edge to rate-limit the ones watching.
    assert resp.status_code == 503
    assert client.calls == 1
    assert slept == []
