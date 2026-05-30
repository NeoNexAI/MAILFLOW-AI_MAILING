"""Tests de autenticación multi-tenant: 401 sin key, aislamiento entre orgs.

Requieren Postgres (fixtures de conftest).
"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("SECRET_KEY", "qdCa5nGhLjd8qY0CCaQP2dE000lbSYDmtPnhzAVeVgs=")


@pytest.fixture()
async def multitenant(session, monkeypatch):
    """Activa AUTH_MODE=multi y crea dos orgs con sus API keys.

    Los routers hacen commit, así que los datos persisten entre tests del módulo;
    usamos slugs únicos por test para evitar colisiones con la restricción unique.
    """
    from app import auth as auth_module
    from app.auth import generate_api_key
    from app.config import settings
    from app.database import get_session
    from app.main import app
    from app.models.organization import Organization

    monkeypatch.setattr(settings, "AUTH_MODE", "multi")
    monkeypatch.setattr(auth_module.settings, "AUTH_MODE", "multi")

    suffix = uuid.uuid4().hex[:8]
    raw_a, hash_a = generate_api_key()
    raw_b, hash_b = generate_api_key()
    org_a = Organization(
        name="A", slug=f"org-a-{suffix}", plan="free", api_key_hash=hash_a
    )
    org_b = Organization(
        name="B", slug=f"org-b-{suffix}", plan="free", api_key_hash=hash_b
    )
    session.add_all([org_a, org_b])
    await session.commit()

    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, raw_a, raw_b
    app.dependency_overrides.clear()


async def test_missing_key_is_401(multitenant):
    client, _raw_a, _raw_b = multitenant
    resp = await client.get("/accounts")
    assert resp.status_code == 401


async def test_invalid_key_is_401(multitenant):
    client, _raw_a, _raw_b = multitenant
    resp = await client.get("/accounts", headers={"X-API-Key": "mf_wrong"})
    assert resp.status_code == 401


async def test_org_cannot_see_another_orgs_accounts(multitenant):
    client, raw_a, raw_b = multitenant
    # Org A crea una cuenta.
    resp = await client.post(
        "/accounts",
        json={"imap_host": "a.example.com", "username": "a@x.com", "password": "p"},
        headers={"X-API-Key": raw_a},
    )
    assert resp.status_code == 201, resp.text
    account_id = resp.json()["id"]

    # Org A la ve.
    resp = await client.get("/accounts", headers={"X-API-Key": raw_a})
    assert len(resp.json()) == 1

    # Org B NO la ve.
    resp = await client.get("/accounts", headers={"X-API-Key": raw_b})
    assert resp.status_code == 200
    assert resp.json() == []

    # Org B no puede acceder a la cuenta de A por id (404, no 403, para no filtrar existencia).
    resp = await client.get(f"/accounts/{account_id}", headers={"X-API-Key": raw_b})
    assert resp.status_code == 404


async def test_bearer_header_also_works(multitenant):
    client, raw_a, _raw_b = multitenant
    resp = await client.get("/accounts", headers={"Authorization": f"Bearer {raw_a}"})
    assert resp.status_code == 200
