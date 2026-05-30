"""Conteo de uso y comprobación de cuotas por organización.

El uso de emails/día se calcula sumando audit_log.emails_processed de los ciclos
de HOY (UTC) de todas las cuentas de la organización.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.audit_log import AuditLog
from app.models.email_account import EmailAccount
from app.plans import account_limit_reached, email_limit_reached


def quotas_enforced() -> bool:
    """Las cuotas de plan solo aplican en SaaS (multi-tenant).

    En self-host single-tenant el uso es ilimitado ("self-host unlimited",
    ver pricing), así que no se aplica ningún límite.
    """
    return settings.AUTH_MODE == "multi"


async def count_accounts(session: AsyncSession, org_id: UUID) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(EmailAccount)
        .where(EmailAccount.org_id == org_id)
    )
    return int(result.scalar() or 0)


async def emails_processed_today(session: AsyncSession, org_id: UUID) -> int:
    """Suma de emails procesados hoy (UTC) por las cuentas de la organización."""
    start = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    result = await session.execute(
        select(func.coalesce(func.sum(AuditLog.emails_processed), 0))
        .select_from(AuditLog)
        .join(EmailAccount, EmailAccount.id == AuditLog.account_id)
        .where(
            EmailAccount.org_id == org_id,
            AuditLog.created_at >= start,
            AuditLog.created_at < end,
        )
    )
    return int(result.scalar() or 0)


async def can_add_account(
    session: AsyncSession, org_id: UUID, plan_key: str | None
) -> bool:
    if not quotas_enforced():
        return True
    current = await count_accounts(session, org_id)
    return not account_limit_reached(plan_key, current)


async def can_process_more(
    session: AsyncSession, org_id: UUID, plan_key: str | None
) -> bool:
    if not quotas_enforced():
        return True
    used = await emails_processed_today(session, org_id)
    return not email_limit_reached(plan_key, used)
