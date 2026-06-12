"""Integración con Stripe (Checkout + Customer Portal + webhooks).

Todo guarded por STRIPE_SECRET_KEY: si no está configurado, las funciones lanzan
BillingNotConfigured y las rutas devuelven 501. El price por plan se resuelve
desde STRIPE_PRICE_PRO / STRIPE_PRICE_TEAM.
"""

from __future__ import annotations

from app.config import settings


class BillingError(Exception):
    """Fallo genérico de billing."""


class BillingNotConfigured(BillingError):
    """Stripe no está configurado (STRIPE_SECRET_KEY vacío)."""


def is_configured() -> bool:
    return bool(settings.STRIPE_SECRET_KEY)


def _client():
    if not is_configured():
        raise BillingNotConfigured("STRIPE_SECRET_KEY not set")
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def price_for_plan(plan_key: str) -> str:
    prices = {"pro": settings.STRIPE_PRICE_PRO, "team": settings.STRIPE_PRICE_TEAM}
    price = prices.get(plan_key, "")
    if not price:
        raise BillingError(f"no Stripe price configured for plan {plan_key!r}")
    return price


def create_checkout_session(
    plan_key: str, org_id: str, customer_id: str | None, seats: int = 1
) -> str:
    """Crea una Checkout Session de suscripción y devuelve su URL.

    `seats` es la cantidad de la línea de suscripción: 1 para pro, nº de
    asientos para team (el plan Team se factura por usuario). El webhook lee
    metadata.seats para fijar organizations.seats.
    """
    stripe = _client()
    params = {
        "mode": "subscription",
        "line_items": [{"price": price_for_plan(plan_key), "quantity": seats}],
        "success_url": settings.BILLING_SUCCESS_URL,
        "cancel_url": settings.BILLING_CANCEL_URL,
        "client_reference_id": org_id,
        "metadata": {"org_id": org_id, "plan": plan_key, "seats": str(seats)},
    }
    if customer_id:
        params["customer"] = customer_id
    session = stripe.checkout.Session.create(**params)
    return session.url


def create_portal_session(customer_id: str) -> str:
    """Crea una sesión del Customer Portal y devuelve su URL."""
    stripe = _client()
    session = stripe.billing_portal.Session.create(
        customer=customer_id, return_url=settings.BILLING_SUCCESS_URL
    )
    return session.url


def parse_webhook(payload: bytes, signature: str) -> dict:
    """Verifica la firma del webhook y devuelve el evento como dict."""
    stripe = _client()
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise BillingNotConfigured("STRIPE_WEBHOOK_SECRET not set")
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as exc:  # noqa: BLE001 — firma inválida / payload corrupto
        raise BillingError(f"invalid webhook signature: {exc}") from exc
    return event
