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
