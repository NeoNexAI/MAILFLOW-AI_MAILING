"""Endpoints de ciclos de procesamiento: historial (audit_log) y disparo manual."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_org
from app.config import settings
from app.database import get_session
from app.models.audit_log import AuditLog
from app.models.email_account import EmailAccount
from app.models.organization import Organization
from app.schemas import CycleEnqueuedOut, CycleOut

logger = logging.getLogger("mailflow.api")

router = APIRouter(prefix="/accounts/{account_id}/cycles", tags=["cycles"])


async def _assert_owned_account(
    account_id: UUID, org: Organization, session: AsyncSession
) -> None:
    exists = (
        await session.execute(
            select(EmailAccount.id).where(
                EmailAccount.id == account_id, EmailAccount.org_id == org.id
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="account_not_found"
        )


@router.get("", response_model=list[CycleOut])
async def list_cycles(
    account_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> list[AuditLog]:
    """Historial de ciclos de una cuenta, más recientes primero."""
    await _assert_owned_account(account_id, org, session)
    rows = await session.execute(
        select(AuditLog)
        .where(AuditLog.account_id == account_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return list(rows.scalars())


@router.post(
    "/run", response_model=CycleEnqueuedOut, status_code=status.HTTP_202_ACCEPTED
)
async def run_cycle_now(
    account_id: UUID,
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> CycleEnqueuedOut:
    """Encola un ciclo inmediato para la cuenta (botón "Run cycle now").

    Usa el mismo job y dedupe job_id que el cron del worker. Si Redis no está
    disponible, devuelve enqueued=false en lugar de fallar la request.
    """
    await _assert_owned_account(account_id, org, session)

    job_id = f"cycle-{account_id}"
    try:
        from arq.connections import RedisSettings, create_pool

        pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        try:
            job = await pool.enqueue_job(
                "process_account_cycle", str(account_id), _job_id=job_id
            )
        finally:
            await pool.close()
        # enqueue_job devuelve None si el job_id ya está en cola (dedupe).
        return CycleEnqueuedOut(
            account_id=account_id,
            enqueued=job is not None,
            job_id=job_id,
        )
    except Exception as exc:  # noqa: BLE001 — no romper la request por Redis
        logger.warning("could not enqueue cycle for %s: %s", account_id, exc)
        return CycleEnqueuedOut(account_id=account_id, enqueued=False, job_id=None)
