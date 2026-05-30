"""Tests de los routers HTTP: CRUD, autenticación y aislamiento por tenant.

Requieren Postgres (usan las fixtures de conftest que crean el schema real).
"""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("SECRET_KEY", "qdCa5nGhLjd8qY0CCaQP2dE000lbSYDmtPnhzAVeVgs=")


@pytest.fixture()
async def app_with_db(session):
    """App FastAPI con get_session apuntando a la sesión de test (sin commits reales).

    Se usa la misma `session` transaccional para el override y para los asserts.
    """
    from app.database import get_session
    from app.main import app

    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
async def client(app_with_db):
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _account_payload(host: str = "imap.example.com") -> dict:
    return {
        "imap_host": host,
        "username": "user@example.com",
        "password": "s3cret",
    }


async def test_single_tenant_autocreates_default_org_and_crud_account(client, session):
    # En modo single (default), no hace falta API key.
    resp = await client.post("/accounts", json=_account_payload())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    account_id = body["id"]
    assert body["imap_host"] == "imap.example.com"
    # El password NUNCA se devuelve.
    assert "password" not in body
    assert "encrypted_credentials" not in body

    # List incluye la cuenta recién creada.
    resp = await client.get("/accounts")
    assert resp.status_code == 200
    assert any(a["id"] == account_id for a in resp.json())

    # Get
    resp = await client.get(f"/accounts/{account_id}")
    assert resp.status_code == 200

    # Patch (cambiar intervalo)
    resp = await client.patch(f"/accounts/{account_id}", json={"interval_minutes": 15})
    assert resp.status_code == 200
    assert resp.json()["interval_minutes"] == 15

    # Delete
    resp = await client.delete(f"/accounts/{account_id}")
    assert resp.status_code == 204
    resp = await client.get(f"/accounts/{account_id}")
    assert resp.status_code == 404


async def test_password_is_encrypted_at_rest(client, session):
    import uuid

    from sqlalchemy import select

    from app.models.email_account import EmailAccount

    resp = await client.post("/accounts", json=_account_payload())
    assert resp.status_code == 201
    account_id = uuid.UUID(resp.json()["id"])

    row = (
        await session.execute(select(EmailAccount).where(EmailAccount.id == account_id))
    ).scalar_one()
    # No debe almacenarse en claro.
    assert "s3cret" not in row.encrypted_credentials


async def test_llm_provider_hides_api_key_but_flags_presence(client, session):
    resp = await client.post(
        "/llm-providers",
        json={
            "label": "OpenAI",
            "type": "openai",
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-secret",
            "default_classification_model": "gpt-4o-mini",
            "default_generation_model": "gpt-4o",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["has_api_key"] is True
    assert "api_key" not in body
    assert "encrypted_api_key" not in body


async def test_rules_require_owned_account(client, session):
    # Crear cuenta.
    account_id = (await client.post("/accounts", json=_account_payload())).json()["id"]
    # Crear regla de dominio.
    resp = await client.post(
        f"/accounts/{account_id}/domain-rules",
        json={"domain": "client.com", "label": "Cliente", "rule_id": "r1"},
    )
    assert resp.status_code == 201, resp.text
    # Listarla.
    resp = await client.get(f"/accounts/{account_id}/domain-rules")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_rules_on_unknown_account_404(client, session):
    import uuid

    fake = uuid.uuid4()
    resp = await client.get(f"/accounts/{fake}/domain-rules")
    assert resp.status_code == 404


async def test_cycles_history_empty_for_new_account(client, session):
    account_id = (await client.post("/accounts", json=_account_payload())).json()["id"]
    resp = await client.get(f"/accounts/{account_id}/cycles")
    assert resp.status_code == 200
    assert resp.json() == []
