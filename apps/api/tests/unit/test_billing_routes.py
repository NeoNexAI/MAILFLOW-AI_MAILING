"""Tests de las rutas de billing y la cuota de cuentas (requieren Postgres)."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("SECRET_KEY", "qdCa5nGhLjd8qY0CCaQP2dE000lbSYDmtPnhzAVeVgs=")


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


def _account_payload(host: str = "imap.example.com") -> dict:
    return {"imap_host": host, "username": "u@example.com", "password": "pw"}


async def test_plan_status_defaults_to_free(client):
    resp = await client.get("/billing/plan")
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] == "free"
    assert body["max_accounts"] == 1
    assert body["max_emails_per_day"] == 100
    assert body["billing_enabled"] is False


async def test_checkout_501_when_billing_not_configured(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "")
    resp = await client.post("/billing/checkout", json={"plan": "pro"})
    assert resp.status_code == 501


async def test_checkout_rejects_invalid_plan(client):
    resp = await client.post("/billing/checkout", json={"plan": "diamond"})
    assert resp.status_code == 400


async def test_free_plan_account_limit_enforced(session, monkeypatch):
    # Las cuotas solo aplican en multi-tenant (SaaS); forzarlo para este test
    # y resolver la org vía override del dependency (sin API key real).
    from app import quota as quota_module
    from app.auth import require_org
    from app.database import get_session
    from app.main import app
    from app.models.email_account import EmailAccount
    from app.models.organization import Organization
    from sqlalchemy import delete

    monkeypatch.setattr(quota_module.settings, "AUTH_MODE", "multi")

    await session.execute(delete(EmailAccount))
    org = Organization(name="Q", slug="quota-test", plan="free")
    session.add(org)
    await session.commit()

    async def _override_session():
        yield session

    async def _override_org():
        return org

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[require_org] = _override_org
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r1 = await c.post("/accounts", json=_account_payload("a.com"))
            assert r1.status_code == 201, r1.text
            r2 = await c.post("/accounts", json=_account_payload("b.com"))
            assert r2.status_code == 402
            assert r2.json()["detail"] == "account_limit_reached"
    finally:
        app.dependency_overrides.clear()


async def test_webhook_invalid_signature_400(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_x")
    resp = await client.post(
        "/billing/webhook",
        content=b'{"type":"x"}',
        headers={"stripe-signature": "bad"},
    )
    assert resp.status_code == 400


async def test_webhook_checkout_completed_upgrades_org_and_dedups(
    client, session, monkeypatch
):
    """Happy path del webhook: checkout.session.completed → plan=pro, idempotente."""
    import uuid

    from app import billing
    from app.models.organization import Organization

    org = Organization(name="W", slug=f"wh-{uuid.uuid4().hex[:8]}", plan="free")
    session.add(org)
    await session.commit()

    event = {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"org_id": str(org.id), "plan": "pro"},
                "customer": "cus_123",
                "subscription": "sub_123",
            }
        },
    }
    # Saltar la verificación de firma: probamos la lógica de aplicación + dedup.
    monkeypatch.setattr(billing, "parse_webhook", lambda payload, sig: event)

    r1 = await client.post(
        "/billing/webhook", content=b"{}", headers={"stripe-signature": "x"}
    )
    assert r1.status_code == 200
    assert r1.json()["status"] == "ok"
    await session.refresh(org)
    assert org.plan == "pro"
    assert org.stripe_subscription_id == "sub_123"

    # Reintento del mismo event.id → deduplicado, no se reaplica.
    r2 = await client.post(
        "/billing/webhook", content=b"{}", headers={"stripe-signature": "x"}
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "duplicate"
