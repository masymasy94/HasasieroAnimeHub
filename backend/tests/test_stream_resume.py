"""Segment proxy must resume after the CDN drops the connection mid-body, without
duplicating or losing bytes, and must never leak an unhandled transport error
out of the streaming generator.
"""
import asyncio

import httpx
import pytest

from app.api.stream import RETRY_ATTEMPTS, proxy_segment


class _FakeResp:
    """One upstream connection attempt: yields `chunks`, then optionally raises."""

    def __init__(self, chunks, raise_exc=None, status_code=200):
        self.status_code = status_code
        self.headers = {}
        self._chunks = chunks
        self._raise_exc = raise_exc

    async def aiter_bytes(self, chunk_size=65536):
        for chunk in self._chunks:
            yield chunk
        if self._raise_exc:
            raise self._raise_exc

    async def aclose(self):
        pass


class _FakeClient:
    """Each instantiation is a new upstream TCP connection (real resumes reconnect)."""

    queue = []  # list[_FakeResp], consumed in creation order — set up by each test
    created = []  # every _FakeClient instance created, for asserting on sent headers

    def __init__(self, *a, **kw):
        self.sent_headers = None
        self._resp = _FakeClient.queue.pop(0)
        _FakeClient.created.append(self)

    def build_request(self, method, url, headers=None):
        self.sent_headers = headers or {}
        return httpx.Request(method, url, headers=headers)

    async def send(self, request, stream=False):
        return self._resp

    async def aclose(self):
        pass



def _fake_request(range_header=None):
    """Stand-in for the starlette Request: headers plus the disconnect probe the
    proxy uses to drop a range the viewer has already seeked away from."""

    async def is_disconnected():
        return False

    return type(
        "Req",
        (),
        {
            "headers": {"range": range_header} if range_header else {},
            "is_disconnected": staticmethod(is_disconnected),
        },
    )()


def _run_proxy_segment(monkeypatch, responses, range_header=None):
    _FakeClient.queue = list(responses)
    _FakeClient.created = []
    monkeypatch.setattr("app.api.stream.httpx.AsyncClient", _FakeClient)

    request = _fake_request(range_header)

    async def go():
        response = await proxy_segment(request=request, url="https://cdn.example/1080p.mp4", headers="{}")
        return b"".join([chunk async for chunk in response.body_iterator])

    return asyncio.run(go())


def test_resume_after_mid_stream_drop_yields_all_bytes_once(monkeypatch):
    exc = httpx.RemoteProtocolError("peer closed connection without sending complete message body")
    body = _run_proxy_segment(
        monkeypatch,
        responses=[
            _FakeResp([b"AAAA", b"BBBB"], raise_exc=exc),
            _FakeResp([b"CCCC"], status_code=206),
        ],
    )
    assert body == b"AAAABBBBCCCC"
    assert len(_FakeClient.created) == 2


def test_resume_after_connection_reset(monkeypatch):
    """A reset connection reaches us as ReadError, not RemoteProtocolError. It used to
    escape the generator as a 500 and freeze the picture; it must resume like a drop."""
    exc = httpx.ReadError("[Errno 104] Connection reset by peer")
    body = _run_proxy_segment(
        monkeypatch,
        responses=[
            _FakeResp([b"AAAA"], raise_exc=exc),
            _FakeResp([b"BBBB"], status_code=206),
        ],
    )
    assert body == b"AAAABBBB"
    assert len(_FakeClient.created) == 2


def test_resume_request_carries_offset_and_preserves_original_range(monkeypatch):
    exc = httpx.RemoteProtocolError("peer closed connection without sending complete message body")
    _run_proxy_segment(
        monkeypatch,
        responses=[
            _FakeResp([b"1234"], raise_exc=exc),  # 4 bytes sent before drop
            _FakeResp([b"5678"], status_code=206),
        ],
        range_header="bytes=1000-1999",
    )
    resume_client = _FakeClient.created[1]
    assert resume_client.sent_headers["Range"] == "bytes=1004-1999"


def test_gives_up_after_max_resumes_without_raising(monkeypatch):
    exc = httpx.RemoteProtocolError("peer closed connection without sending complete message body")
    # initial fetch + RETRY_ATTEMPTS resumes, all dropping — the last one exhausts the budget
    responses = [_FakeResp([b"x"], raise_exc=exc, status_code=206) for _ in range(RETRY_ATTEMPTS + 1)]
    body = _run_proxy_segment(monkeypatch, responses=responses)
    assert body == b"x" * (RETRY_ATTEMPTS + 1)
    assert len(_FakeClient.created) == RETRY_ATTEMPTS + 1


def test_resume_with_non_206_status_is_rejected_not_duplicated(monkeypatch):
    """CDN ignores our Range and answers 200 (full body from byte 0) — must not be
    stitched onto what we already sent, or the client gets a duplicated prefix."""
    exc = httpx.RemoteProtocolError("peer closed connection without sending complete message body")
    body = _run_proxy_segment(
        monkeypatch,
        responses=[
            _FakeResp([b"AAAA"], raise_exc=exc),
            _FakeResp([b"AAAA", b"BBBB"], status_code=200),  # ignored the Range we sent
        ],
    )
    assert body == b"AAAA"  # stream aborted right after the drop, no duplicated bytes
    assert len(_FakeClient.created) == 2  # the bad resume attempt did happen, just got discarded


def test_unrecognized_range_disables_resume(monkeypatch):
    """A suffix range ('bytes=-500') can't be turned into a safe absolute offset —
    resume must not be attempted; the drop propagates like it did before this feature."""
    exc = httpx.RemoteProtocolError("peer closed connection without sending complete message body")
    _FakeClient.queue = [_FakeResp([b"AAAA"], raise_exc=exc)]
    _FakeClient.created = []
    monkeypatch.setattr("app.api.stream.httpx.AsyncClient", _FakeClient)
    request = _fake_request("bytes=-500")

    async def go():
        response = await proxy_segment(request=request, url="https://cdn.example/1080p.mp4", headers="{}")
        return b"".join([chunk async for chunk in response.body_iterator])

    with pytest.raises(httpx.RemoteProtocolError):
        asyncio.run(go())
    assert len(_FakeClient.created) == 1  # no resume attempt was made
