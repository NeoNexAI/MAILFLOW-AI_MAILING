"""Rutas de billing: plan actual + uso, checkout, portal y webhook de Stripe."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import billing, quota
from app.auth import require_org
from app.database import get_session
from app.models.organization import Organization
from app.models.stripe_event import StripeEvent
from app.plans import get_plan

logger = logging.getLogger("mailflow.api")

router = APIRouter(prefix="/billing", tags=["billing"])


class PlanStatus(BaseModel):
    plan: str
    label: str
    max_accounts: int | None
    max_emails_per_day: int | None
    accounts_used: int
    emails_today: int
    billing_enabled: bool


class CheckoutRequest(BaseModel):
    plan: str  # "pro" | "team"


class UrlResponse(BaseModel):
    url: str


@router.get("/plan", response_model=PlanStatus)
async def plan_status(
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> PlanStatus:
    plan = get_plan(org.plan)
    return PlanStatus(
        plan=plan.key,
        label=plan.label,
        max_accounts=plan.max_accounts,
        max_emails_per_day=plan.max_emails_per_day,
        accounts_used=await quota.count_accounts(session, org.id),
        emails_today=await quota.emails_processed_today(session, org.id),
        billing_enabled=billing.is_configured(),
    )


@router.post("/checkout", response_model=UrlResponse)
async def checkout(
    payload: CheckoutRequest,
    org: Organization = Depends(require_org),
) -> UrlResponse:
    if payload.plan not in ("pro", "team"):
        raise HTTPException(status_code=400, detail="invalid_plan")
    try:
        # Las llamadas al SDK de Stripe son síncronas → a un hilo.
        url = await asyncio.to_thread(
            billing.create_checkout_session,
            payload.plan,
            str(org.id),
            org.stripe_customer_id,
        )
    except billing.BillingNotConfigured as exc:
        raise HTTPException(status_code=501, detail="billing_not_configured") from exc
    except billing.BillingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UrlResponse(url=url)


@router.post("/portal", response_model=UrlResponse)
async def portal(org: Organization = Depends(require_org)) -> UrlResponse:
    if not org.stripe_customer_id:
        raise HTTPException(status_code=400, detail="no_customer")
    try:
        url = await asyncio.to_thread(
            billing.create_portal_session, org.stripe_customer_id
        )
    except billing.BillingNotConfigured as exc:
        raise HTTPException(status_code=501, detail="billing_not_configured") from exc
    return UrlResponse(url=url)


@router.post("/webhook")
async def webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Webhook de Stripe: actualiza plan/suscripción de la organización.

    El callback no pasa por require_org; la confianza viene de la firma del
    webhook (STRIPE_WEBHOOK_SECRET).
    """
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        # La verificación de firma del SDK de Stripe es síncrona → a un hilo.
        event = await asyncio.to_thread(billing.parse_webhook, payload, signature)
    except billing.BillingNotConfigured as exc:
        raise HTTPException(status_code=501, detail="billing_not_configured") from exc
    except billing.BillingError as exc:
        raise HTTPException(status_code=400, detail="invalid_signature") from exc

    # Idempotencia: Stripe reintenta. Si ya procesamos este event.id, salimos.
    event_id = event.get("id")
    if event_id:
        inserted = await session.execute(
            pg_insert(StripeEvent)
            .values(id=event_id)
            .on_conflict_do_nothing(index_elements=["id"])
            .returning(StripeEvent.id)
        )
        await session.commit()
        if inserted.scalar_one_or_none() is None:
            return {"status": "duplicate"}

    await _apply_event(session, event)
    return {"status": "ok"}


async def _apply_event(session: AsyncSession, event: dict) -> None:
    """Aplica los eventos relevantes de Stripe al estado de la organización."""
    etype = event.get("type", "")
    obj = event.get("data", {}).get("object", {})

    if etype == "checkout.session.completed":
        org_id = (obj.get("metadata") or {}).get("org_id") or obj.get(
            "client_reference_id"
        )
        plan = (obj.get("metadata") or {}).get("plan", "pro")
        org = await _org(session, org_id)
        if org:
            org.plan = plan
            org.stripe_customer_id = obj.get("customer") or org.stripe_customer_id
            org.stripe_subscription_id = (
                obj.get("subscription") or org.stripe_subscription_id
            )
            await session.commit()
            logger.info("org %s upgraded to %s", org_id, plan)

    elif etype in ("customer.subscription.deleted", "customer.subscription.canceled"):
        sub_id = obj.get("id")
        org = await _org_by_subscription(session, sub_id)
        if org:
            org.plan = "free"
            await session.commit()
            logger.info("org %s downgraded to free (subscription ended)", org.id)


async def _org(session: AsyncSession, org_id: str | None) -> Organization | None:
    if not org_id:
        return None
    return (
        await session.execute(select(Organization).where(Organization.id == org_id))
    ).scalar_one_or_none()


async def _org_by_subscription(
    session: AsyncSession, sub_id: str | None
) -> Organization | None:
    if not sub_id:
        return None
    return (
        await session.execute(
            select(Organization).where(Organization.stripe_subscription_id == sub_id)
        )
    ).scalar_one_or_none()
