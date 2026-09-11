import asyncio

import httpx
import pytest

from app.api.stream import RETRY_ATTEMPTS, SEND_RETRY_MAX_SECONDS, _send_with_retry


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
