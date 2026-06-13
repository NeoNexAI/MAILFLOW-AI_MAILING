"""Endpoint /metrics en formato Prometheus (exposición de texto).

Métricas básicas agregadas desde `audit_log` (que escribe el worker) y
`email_accounts`. Al leer de la DB, los contadores reflejan el procesamiento
real con independencia del proceso (api vs worker).

No expone datos por organización ni PII, solo totales del despliegue. Como
`/health`, va sin autenticar: restríngelo a la red de scraping en el reverse
proxy si la instancia es pública.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response
from sqlalchemy import func, select

from app.database import async_session_factory
from app.models.audit_log import AuditLog
from app.models.email_account import EmailAccount

router = APIRouter(tags=["metrics"])

log = logging.getLogger("mailflow.metrics")

CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def _render(metrics: list[tuple[str, str, str, int]]) -> str:
    """Serializa (name, type, help, value) en formato de exposición Prometheus."""
    lines: list[str] = []
    for name, mtype, help_text, value in metrics:
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} {mtype}")
        lines.append(f"{name} {value}")
    return "\n".join(lines) + "\n"


@router.get("/metrics")
async def metrics() -> Response:
    """Expone contadores básicos de procesamiento para Prometheus."""
    up = 1
    cycles = emails = drafts = errors = accounts = 0
    try:
        async with async_session_factory() as session:
            row = (
                await session.execute(
                    select(
                        func.count(AuditLog.id),
                        func.coalesce(func.sum(AuditLog.emails_processed), 0),
                        func.coalesce(func.sum(AuditLog.drafts_saved), 0),
                        func.coalesce(func.sum(AuditLog.error_count), 0),
                    )
                )
            ).one()
            cycles, emails, drafts, errors = (int(v) for v in row)
            accounts = int(
                (
                    await session.execute(select(func.count(EmailAccount.id)))
                ).scalar_one()
            )
    except Exception as exc:  # noqa: BLE001 — un scrape nunca debe romper
        up = 0
        log.warning("metrics DB probe failed: %s", exc)

    body = _render(
        [
            ("mailflow_up", "gauge", "1 if the API can read the database, else 0.", up),
            ("mailflow_cycles_total", "counter", "Processing cycles recorded.", cycles),
            (
                "mailflow_emails_processed_total",
                "counter",
                "Emails processed across all cycles.",
                emails,
            ),
            (
                "mailflow_drafts_saved_total",
                "counter",
                "Draft replies saved across all cycles.",
                drafts,
            ),
            (
                "mailflow_errors_total",
                "counter",
                "Per-email errors across all cycles.",
                errors,
            ),
            (
                "mailflow_accounts_total",
                "gauge",
                "Configured email accounts.",
                accounts,
            ),
        ]
    )
    return Response(
        content=body,
        media_type=CONTENT_TYPE,
        headers={"Cache-Control": "no-store"},
    )
