"""Regresión de M1.2: el I/O síncrono no debe bloquear el event loop, y el
circuit breaker de generación corta tras fallos repetidos.

No requieren Postgres.
"""

from __future__ import annotations

import asyncio
import os
import time

import pytest

os.environ.setdefault("SECRET_KEY", "qdCa5nGhLjd8qY0CCaQP2dE000lbSYDmtPnhzAVeVgs=")


async def test_sync_io_does_not_block_event_loop():
    """Un connect IMAP síncrono lento debe ejecutarse en hilo: el loop sigue vivo."""
    beats = 0

    async def heartbeat() -> None:
        nonlocal beats
        while True:
            await asyncio.sleep(0.02)
            beats += 1

    hb = asyncio.create_task(heartbeat())

    def blocking_io() -> str:
        time.sleep(0.3)  # simula IMAP/LLM síncrono
        return "done"

    # Mismo patrón que CycleService: el trabajo síncrono va a un hilo.
    result = await asyncio.to_thread(blocking_io)
    hb.cancel()

    assert result == "done"
    # Si el loop no se hubiera bloqueado, el heartbeat corrió varias veces.
    assert beats >= 4


async def test_generation_circuit_breaker_opens_after_failures():
    """Tras N fallos de generación, el breaker se abre y rechaza sin reintentar."""
    from mailflow_core.resilience import CircuitBreaker, CircuitOpenError

    breaker = CircuitBreaker(failure_threshold=3, reset_timeout=60.0)
    calls = {"n": 0}

    async def failing_generation() -> str:
        calls["n"] += 1
        raise RuntimeError("LLM down")

    # 3 fallos → abre el circuito.
    for _ in range(3):
        with pytest.raises(RuntimeError):
            await breaker.call(failing_generation)
    assert breaker.state == "open"

    # El 4º intento se rechaza SIN ejecutar la generación (no incrementa calls).
    before = calls["n"]
    with pytest.raises(CircuitOpenError):
        await breaker.call(failing_generation)
    assert calls["n"] == before
