"""The Fire TV app parses /api/search as plain JSON, not SSE (it crashed/showed nothing)."""
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.client_log import router as client_log_router
from app.api.deps import get_provider_registry
from app.api.search import router as search_router
from app.schemas.anime import AnimeSearchResult


class _Provider:
    def __init__(self, site_id, results=None, fail=False):
        self.site_id, self._results, self._fail = site_id, results or [], fail

    async def search(self, title):
        if self._fail:
            raise RuntimeError("boom")
        return list(self._results)


class _Registry:
    def all_providers(self):
        return [
            _Provider("animeunity", [AnimeSearchResult(id=1, slug="a", title="Lara")]),
            _Provider("broken", fail=True),
        ]


app = FastAPI()
app.include_router(search_router, prefix="/api")
app.include_router(client_log_router, prefix="/api")
app.dependency_overrides[get_provider_registry] = lambda: _Registry()
client = TestClient(app)


def test_search_json_format_returns_plain_json():
    r = client.get("/api/search", params={"title": "lara", "format": "json"})
    assert r.headers["content-type"].startswith("application/json")
    assert [(x["id"], x["source_site"]) for x in r.json()["results"]] == [(1, "animeunity")]


def test_search_default_still_streams_sse_for_the_web_ui():
    r = client.get("/api/search", params={"title": "lara"})
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "event: done" in r.text


def test_client_log_lands_in_server_log(caplog):
    with caplog.at_level(logging.INFO, logger="animehub.tv"):
        r = client.post("/api/client-log", json=[
            {"level": "E", "tag": "Crash", "message": "java.lang.IllegalStateException\n\tat x"},
        ])
    assert r.status_code == 204
    assert "IllegalStateException" in caplog.text
    assert caplog.records[0].levelno == logging.ERROR
