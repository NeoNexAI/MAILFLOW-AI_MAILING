"""Definición de planes y sus límites. Lógica de negocio pura (sin I/O)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    """Un plan de suscripción y sus límites.

    `max_accounts` / `max_emails_per_day` en None significa ilimitado.
    """

    key: str
    label: str
    max_accounts: int | None
    max_emails_per_day: int | None


PLANS: dict[str, Plan] = {
    "free": Plan("free", "Free", max_accounts=1, max_emails_per_day=100),
    "pro": Plan("pro", "Pro", max_accounts=None, max_emails_per_day=None),
    "team": Plan("team", "Team", max_accounts=None, max_emails_per_day=None),
}

DEFAULT_PLAN = "free"


def get_plan(key: str | None) -> Plan:
    """Devuelve el Plan para una clave; cae a free si es desconocida/None."""
    return PLANS.get(key or "", PLANS[DEFAULT_PLAN])


def account_limit_reached(plan_key: str | None, current_accounts: int) -> bool:
    limit = get_plan(plan_key).max_accounts
    return limit is not None and current_accounts >= limit


def email_limit_reached(plan_key: str | None, emails_today: int) -> bool:
    limit = get_plan(plan_key).max_emails_per_day
    return limit is not None and emails_today >= limit
