"""Tests del middleware de request-id y de la init guardada de Sentry."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("SECRET_KEY", "qdCa5nGhLjd8qY0CCaQP2dE000lbSYDmtPnhzAVeVgs=")


@pytest.fixture()
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_request_id_generated_and_returned(client):
    # La ruta "/" no toca DB: ideal para probar el middleware aislado.
    resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID")
    assert "X-Response-Time-ms" in resp.headers


async def test_request_id_echoes_incoming(client):
    resp = await client.get("/", headers={"X-Request-ID": "abc-123"})
    assert resp.headers["X-Request-ID"] == "abc-123"


def test_init_sentry_noop_without_dsn(monkeypatch):
    from app import observability
    from app.config import settings

    monkeypatch.setattr(settings, "SENTRY_DSN", "")
    assert observability.init_sentry() is False


def test_init_sentry_active_with_dsn(monkeypatch):
    from app import observability
    from app.config import settings

    captured: dict = {}

    def fake_init(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(settings, "SENTRY_DSN", "https://x@example.test/1")
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    import sentry_sdk

    monkeypatch.setattr(sentry_sdk, "init", fake_init)
    assert observability.init_sentry() is True
    assert captured["dsn"] == "https://x@example.test/1"
    assert captured["environment"] == "staging"


def test_init_sentry_never_raises(monkeypatch):
    from app import observability
    from app.config import settings

    monkeypatch.setattr(settings, "SENTRY_DSN", "https://x@example.test/1")
    import sentry_sdk

    def boom(**kwargs):
        raise RuntimeError("sdk down")

    monkeypatch.setattr(sentry_sdk, "init", boom)
    # Un fallo de observabilidad no debe propagar.
    assert observability.init_sentry() is False
