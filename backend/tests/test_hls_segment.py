"""A vixcloud edge that answers 503 sends an error page, not video: the segment must
be retried (on the next edge) instead of being written into the .ts as if it were data.
"""
import asyncio

import app.services.download_worker as dw
from app.services.download_worker import DownloadWorker


class _Resp:
    def __init__(self, status_code: int, content: bytes):
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _Session:
    """503 from au-d1-03, video bytes from any other edge."""

    def __init__(self):
        self.urls = []

    async def get(self, url, headers=None):
        self.urls.append(url)
        if "au-d1-03" in url:
            return _Resp(503, b"<html>temporarily unavailable</html>")
        return _Resp(200, b"\x47video")


def test_503_segment_is_retried_on_next_edge(monkeypatch):
    monkeypatch.setattr(dw, "SEGMENT_RETRY_DELAY", 0)
    session = _Session()
    url = "https://au-d1-03.vix-content.net/hls/seg-1.ts?token=abc&expires=1"

    data = asyncio.run(DownloadWorker._download_segment(session, url, {}))

    assert data == b"\x47video"
    assert session.urls[1] == "https://au-d1-04.vix-content.net/hls/seg-1.ts?token=abc&expires=1"
