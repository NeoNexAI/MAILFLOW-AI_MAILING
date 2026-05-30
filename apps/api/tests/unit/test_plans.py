"""Tests de la lógica de planes (pura)."""

from __future__ import annotations

from app.plans import (
    account_limit_reached,
    email_limit_reached,
    get_plan,
)


def test_get_plan_falls_back_to_free():
    assert get_plan(None).key == "free"
    assert get_plan("nonsense").key == "free"
    assert get_plan("pro").key == "pro"


def test_free_account_limit():
    assert account_limit_reached("free", 1) is True
    assert account_limit_reached("free", 0) is False


def test_paid_plans_unlimited_accounts():
    assert account_limit_reached("pro", 999) is False
    assert account_limit_reached("team", 999) is False


def test_free_email_limit():
    assert email_limit_reached("free", 100) is True
    assert email_limit_reached("free", 99) is False


def test_paid_plans_unlimited_emails():
    assert email_limit_reached("pro", 10_000) is False
    assert email_limit_reached("team", 10_000) is False
