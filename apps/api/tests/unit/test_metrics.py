"""Tests del endpoint /metrics (formato Prometheus)."""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("SECRET_KEY", "qdCa5nGhLjd8qY0CCaQP2dE000lbSYDmtPnhzAVeVgs=")


def _parse(text: str) -> dict[str, float]:
    """Extrae {metric: value} ignorando comentarios HELP/TYPE."""
    out: dict[str, float] = {}
    for line in text.splitlines():
        if line and not line.startswith("#"):
            name, value = line.split(" ", 1)
            out[name] = float(value)
    return out


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


async def test_metrics_aggregates_from_audit_log(client, session):
    from app.models.audit_log import AuditLog
    from app.models.email_account import EmailAccount
    from app.models.organization import Organization

    org = Organization(name="M", slug=f"metrics-{uuid.uuid4().hex[:8]}", plan="free")
    session.add(org)
    await session.commit()
    account = EmailAccount(
        org_id=org.id,
        imap_host="imap.example.com",
        username=f"{uuid.uuid4().hex[:8]}@example.com",
        encrypted_credentials="x",
    )
    session.add(account)
    await session.commit()
    session.add(
        AuditLog(
            account_id=account.id,
            cycle_id=uuid.uuid4(),
            emails_processed=5,
            drafts_saved=3,
            error_count=1,
        )
    )
    await session.commit()

    # El endpoint usa async_session_factory directamente: lo apuntamos a la
    # misma sesión de test para ver las filas recién insertadas.
    @asynccontextmanager
    async def _factory():
        yield session

    with patch("app.routers.metrics.async_session_factory", _factory):
        resp = await client.get("/metrics")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    parsed = _parse(resp.text)
    assert parsed["mailflow_up"] == 1
    assert parsed["mailflow_cycles_total"] >= 1
    assert parsed["mailflow_emails_processed_total"] >= 5
    assert parsed["mailflow_drafts_saved_total"] >= 3
    assert parsed["mailflow_errors_total"] >= 1
    assert parsed["mailflow_accounts_total"] >= 1
    # Formato Prometheus: incluye las cabeceras HELP/TYPE.
    assert "# TYPE mailflow_cycles_total counter" in resp.text


def test_metrics_db_down_reports_up_zero():
    from app.main import app

    @asynccontextmanager
    async def _broken_factory():
        raise RuntimeError("db down")
        yield  # pragma: no cover

    tc = TestClient(app, raise_server_exceptions=False)
    with patch("app.routers.metrics.async_session_factory", _broken_factory):
        resp = tc.get("/metrics")

    assert resp.status_code == 200
    assert "mailflow_up 0" in resp.text
