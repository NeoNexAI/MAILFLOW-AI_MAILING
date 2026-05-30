"""MailFlow API — entry point."""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import async_session_factory

logger = logging.getLogger("mailflow.api")

app = FastAPI(
    title="MailFlow API",
    version="0.1.0",
    description="Open source AI email assistant API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> JSONResponse:
    """Readiness probe: comprueba conectividad con la base de datos.

    Devuelve 200 si la DB responde, 503 si no. Pensado para monitores de
    uptime y orquestadores (Docker healthcheck, k8s readiness).
    """
    started = time.monotonic()
    db_ok = False
    error: str | None = None
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # noqa: BLE001 — health must never raise
        error = str(exc)
        logger.warning("health check DB probe failed: %s", error)

    payload: dict[str, object] = {
        "status": "ok" if db_ok else "degraded",
        "db": "up" if db_ok else "down",
        "version": "0.1.0",
        "latency_ms": round((time.monotonic() - started) * 1000, 1),
    }
    if error:
        payload["error"] = error
    return JSONResponse(
        payload,
        status_code=200 if db_ok else 503,
        headers={"Cache-Control": "no-store"},
    )


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "MailFlow API", "docs": "/docs"}
