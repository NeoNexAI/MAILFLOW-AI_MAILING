"""Tests para el endpoint /health.

No requieren Postgres: se mockea la session factory para cubrir tanto el
camino "DB up" (200) como "DB down" (503).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


def test_health_db_up_returns_200():
    @asynccontextmanager
    async def fake_factory():
        session = MagicMock()
        session.execute = AsyncMock(return_value=None)
        yield session

    with patch("app.main.async_session_factory", fake_factory):
        resp = _client().get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "up"
    assert "latency_ms" in body
    assert resp.headers["cache-control"] == "no-store"


def test_health_db_down_returns_503():
    @asynccontextmanager
    async def failing_factory():
        raise ConnectionError("no route to host")
        yield  # pragma: no cover

    with patch("app.main.async_session_factory", failing_factory):
        resp = _client().get("/health")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["db"] == "down"
    assert "error" in body


def test_root_returns_docs_link():
    resp = _client().get("/")
    assert resp.status_code == 200
    assert resp.json()["docs"] == "/docs"
