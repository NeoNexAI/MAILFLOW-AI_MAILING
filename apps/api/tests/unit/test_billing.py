"""Tests de billing: comportamiento sin Stripe configurado + parsing seguro."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SECRET_KEY", "qdCa5nGhLjd8qY0CCaQP2dE000lbSYDmtPnhzAVeVgs=")


def test_not_configured_by_default(monkeypatch):
    from app import billing
    from app.config import settings

    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "")
    assert billing.is_configured() is False
    with pytest.raises(billing.BillingNotConfigured):
        billing.create_checkout_session("pro", "org-1", None)


def test_price_for_plan_requires_config(monkeypatch):
    from app import billing
    from app.config import settings

    monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "")
    with pytest.raises(billing.BillingError):
        billing.price_for_plan("pro")

    monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "price_123")
    assert billing.price_for_plan("pro") == "price_123"


def test_parse_webhook_not_configured(monkeypatch):
    from app import billing
    from app.config import settings

    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "")
    with pytest.raises(billing.BillingNotConfigured):
        billing.parse_webhook(b"{}", "sig")


def test_checkout_session_passes_seats_as_quantity(monkeypatch):
    """Team por asientos: quantity y metadata.seats reflejan los seats pedidos."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app import billing
    from app.config import settings

    monkeypatch.setattr(settings, "STRIPE_PRICE_TEAM", "price_team")
    captured: dict = {}

    fake_stripe = MagicMock()

    def fake_create(**params):
        captured.update(params)
        return SimpleNamespace(url="https://checkout.example/cs_test")

    fake_stripe.checkout.Session.create.side_effect = fake_create
    monkeypatch.setattr(billing, "_client", lambda: fake_stripe)

    url = billing.create_checkout_session("team", "org-1", None, seats=5)

    assert url == "https://checkout.example/cs_test"
    assert captured["line_items"] == [{"price": "price_team", "quantity": 5}]
    assert captured["metadata"]["seats"] == "5"
    assert captured["metadata"]["plan"] == "team"
