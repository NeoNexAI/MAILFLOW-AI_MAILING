"""ARQ worker entry point — reemplaza el stub de Fase 1."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from app.config import settings
from app.database import async_session_factory
from app.repositories.account import AccountRepository
from app.services.cycle import CycleService
from arq import cron
from arq.connections import RedisSettings

log = logging.getLogger("mailflow.worker")


async def on_startup(ctx: dict) -> None:
    """Inicializa recursos compartidos en el contexto ARQ."""
    ctx["session_factory"] = async_session_factory


async def process_account_cycle(ctx: dict, account_id: str) -> dict:
    """Job ARQ principal. account_id como str para serialización JSON/Redis.

    Resiliencia:
    - CycleService.run() captura internamente los fallos de IMAP/LLM por email
      (con reintentos+backoff) y registra el resultado en audit_log, así que el
      camino normal no lanza.
    - Si run() lanzara igualmente (p.ej. DB caída al claim/finalize), dejamos que
      la excepción propague para que ARQ reintente el job (MAX_TRIES). Cuando se
      agotan los reintentos, ARQ invoca on_job_failure → dead-letter logging.
    """
    job_try = ctx.get("job_try", 1)
    log.info("cycle start account=%s try=%d", account_id, job_try)
    service = CycleService(ctx["session_factory"])
    result = await service.run(UUID(account_id))
    log.info(
        "cycle done account=%s emails=%d drafts=%d errors=%d",
        account_id,
        result.emails_processed,
        result.drafts_saved,
        result.errors,
    )
    return {
        "account_id": account_id,
        "cycle_id": str(result.cycle_id),
        "emails_processed": result.emails_processed,
        "drafts_saved": result.drafts_saved,
        "errors": result.errors,
    }


async def on_job_failure(ctx: dict, exc: BaseException) -> None:
    """Dead-letter hook: registra los jobs que agotaron todos los reintentos.

    ARQ llama a este hook cuando un job falla definitivamente. Aquí lo dejamos
    trazado de forma estructurada; un sink externo (Sentry/alertas) puede
    engancharse a estos logs.
    """
    job_id = ctx.get("job_id")
    func = ctx.get("job_name") or ctx.get("function")
    log.error(
        "DEAD-LETTER job_id=%s func=%s exhausted retries: %s: %s",
        job_id,
        func,
        type(exc).__name__,
        exc,
    )


async def schedule_cycles(ctx: dict) -> None:
    """Cron cada 5 min: encola ciclos para cuentas que toca procesar.

    ARQ deduplicación: _job_id=f"cycle-{account.id}" evita encolar
    la misma cuenta dos veces si el cron se solapa.
    """
    now = datetime.now(tz=UTC)
    async with ctx["session_factory"]() as session:
        accounts = await AccountRepository(session).get_accounts_due(now)

    redis = ctx["redis"]
    for account in accounts:
        await redis.enqueue_job(
            "process_account_cycle",
            str(account.id),
            _job_id=f"cycle-{account.id}",
        )
    log.info("Scheduled %d account cycles", len(accounts))


class WorkerSettings:
    functions = [process_account_cycle]
    cron_jobs = [cron(schedule_cycles, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55})]
    on_startup = on_startup
    on_job_failure = on_job_failure
    # Reintentos a nivel de job: ante un fallo no capturado (p.ej. DB caída),
    # ARQ reencola con backoff propio hasta agotar max_tries → dead-letter.
    max_tries = 3
    # Un ciclo no debería tardar más de unos minutos; corta cuelgues de IMAP/LLM.
    job_timeout = 300
    queue_name = "mailflow:default"
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
