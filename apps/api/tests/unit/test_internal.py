"""Tests del endpoint interno de aprovisionamiento (POST /internal/orgs).

Requieren Postgres (usan las fixtures de conftest que crean el schema real).
El endpoint solo lo consume el servidor web (Better Auth) server-to-server,
autenticado con el secreto compartido INTERNAL_API_SECRET.
"""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("SECRET_KEY", "qdCa5nGhLjd8qY0CCaQP2dE000lbSYDmtPnhzAVeVgs=")

SECRET = "test-internal-secret"


@pytest.fixture()
async def client(session):
    from app.database import get_session
    from app.main import app

    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_disabled_returns_501_when_secret_unset(client, monkeypatch):
    """Sin INTERNAL_API_SECRET configurado, el endpoint queda desactivado (501)."""
    from app.config import settings

    monkeypatch.setattr(settings, "INTERNAL_API_SECRET", "")
    resp = await client.post(
        "/internal/orgs",
        json={"name": "Acme"},
        headers={"X-Internal-Secret": "anything"},
    )
    assert resp.status_code == 501
    assert resp.json()["detail"] == "internal_api_disabled"


async def test_forbidden_without_secret_header(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "INTERNAL_API_SECRET", SECRET)
    resp = await client.post("/internal/orgs", json={"name": "Acme"})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "forbidden"


async def test_forbidden_with_wrong_secret(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "INTERNAL_API_SECRET", SECRET)
    resp = await client.post(
        "/internal/orgs",
        json={"name": "Acme"},
        headers={"X-Internal-Secret": "wrong"},
    )
    assert resp.status_code == 403


async def test_creates_org_and_returns_api_key(client, session, monkeypatch):
    import uuid

    from sqlalchemy import select

    from app.auth import hash_api_key
    from app.config import settings
    from app.models.organization import Organization

    monkeypatch.setattr(settings, "INTERNAL_API_SECRET", SECRET)
    name = f"Acme {uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/internal/orgs",
        json={"name": name},
        headers={"X-Internal-Secret": SECRET},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["org_id"]
    assert body["slug"]
    # La API key en claro viaja una sola vez y lleva el prefijo mf_.
    assert body["api_key"].startswith("mf_")

    # Persistida: solo se guarda el hash, nunca la clave en claro.
    org = (
        await session.execute(
            select(Organization).where(Organization.id == uuid.UUID(body["org_id"]))
        )
    ).scalar_one()
    assert org.name == name
    assert org.api_key_hash == hash_api_key(body["api_key"])
    assert org.plan == "free"


async def test_slug_collision_gets_unique_suffix(client, session, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "INTERNAL_API_SECRET", SECRET)

    r1 = await client.post(
        "/internal/orgs",
        json={"name": "Repeated Name", "slug": "dup-slug"},
        headers={"X-Internal-Secret": SECRET},
    )
    r2 = await client.post(
        "/internal/orgs",
        json={"name": "Repeated Name", "slug": "dup-slug"},
        headers={"X-Internal-Secret": SECRET},
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    slug1 = r1.json()["slug"]
    slug2 = r2.json()["slug"]
    assert slug1 == "dup-slug"
    assert slug2 != slug1
    assert slug2.startswith("dup-slug-")
