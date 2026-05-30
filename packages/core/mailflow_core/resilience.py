"""Utilidades de resiliencia: reintentos con backoff y circuit breaker.

Framework-agnóstico (sin dependencias de FastAPI/ARQ), reutilizable por el
worker y por cualquier llamada a servicios externos inestables (IMAP, LLM).

- retry_with_backoff: reintenta una operación con espera exponencial + jitter.
- CircuitBreaker: corta llamadas a un dependiente que falla repetidamente,
  evitando martillearlo (y acelerando el fallo) hasta que pase un cooldown.
"""

from __future__ import annotations

import asyncio
import functools
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from mailflow_core.exceptions import MailFlowError


class CircuitOpenError(MailFlowError):
    """Se lanza cuando el circuito está abierto y la llamada se rechaza sin intentarla."""


@dataclass
class RetryPolicy:
    """Parámetros de reintento con backoff exponencial y jitter."""

    max_attempts: int = 3
    base_delay: float = 0.5  # segundos
    max_delay: float = 30.0
    factor: float = 2.0
    jitter: float = 0.1  # fracción aleatoria añadida al delay

    def delay_for(self, attempt: int) -> float:
        """Delay (segundos) antes del intento `attempt` (1-indexed, attempt>=1)."""
        raw = self.base_delay * (self.factor ** (attempt - 1))
        capped = min(raw, self.max_delay)
        return capped + random.random() * self.jitter * capped


async def retry_with_backoff[T](
    operation: Callable[[], Awaitable[T]],
    *,
    policy: RetryPolicy | None = None,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    on_retry: Callable[[int, BaseException], None] | None = None,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> T:
    """Ejecuta `operation` reintentando ante `retry_on` con espera exponencial.

    Args:
        operation: corutina sin argumentos a ejecutar.
        policy: parámetros de reintento (por defecto RetryPolicy()).
        retry_on: tipos de excepción que disparan reintento. Otras se propagan.
        on_retry: callback (intento, excepción) invocado tras cada fallo
            reintentable (útil para logging).
        sleep: función de espera asíncrona inyectable (para tests). Por defecto
            asyncio.sleep.

    Returns:
        El resultado de `operation`.

    Raises:
        La última excepción si se agotan los intentos, o cualquier excepción
        no incluida en `retry_on`.
    """
    pol = policy or RetryPolicy()
    if sleep is None:
        sleep = asyncio.sleep

    last_exc: BaseException | None = None
    for attempt in range(1, pol.max_attempts + 1):
        try:
            return await operation()
        except retry_on as exc:
            last_exc = exc
            if attempt >= pol.max_attempts:
                break
            if on_retry is not None:
                on_retry(attempt, exc)
            await sleep(pol.delay_for(attempt))
    assert last_exc is not None  # noqa: S101 — invariante: el loop falló al menos una vez
    raise last_exc


@dataclass
class CircuitBreaker:
    """Circuit breaker simple con estados closed → open → half-open.

    - closed: las llamadas pasan. Tras `failure_threshold` fallos consecutivos
      el circuito se abre.
    - open: las llamadas se rechazan con CircuitOpenError hasta que transcurre
      `reset_timeout` segundos; entonces pasa a half-open.
    - half-open: se permite una llamada de prueba. Si tiene éxito, el circuito
      se cierra; si falla, vuelve a abrirse.
    """

    failure_threshold: int = 5
    reset_timeout: float = 60.0
    _failures: int = field(default=0, init=False)
    _opened_at: float | None = field(default=None, init=False)
    _time: Callable[[], float] = field(default=time.monotonic)

    @property
    def state(self) -> str:
        if self._opened_at is None:
            return "closed"
        if self._time() - self._opened_at >= self.reset_timeout:
            return "half-open"
        return "open"

    def _on_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def _on_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = self._time()

    async def call[T](self, operation: Callable[[], Awaitable[T]]) -> T:
        """Ejecuta `operation` respetando el estado del circuito."""
        if self.state == "open":
            raise CircuitOpenError(f"Circuit open ({self._failures} failures); rejecting call")
        try:
            result = await operation()
        except Exception:
            self._on_failure()
            raise
        else:
            self._on_success()
            return result


def with_retry[T](
    *,
    policy: RetryPolicy | None = None,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorador async que aplica retry_with_backoff a una corutina."""

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: object, **kwargs: object) -> T:
            return await retry_with_backoff(
                lambda: func(*args, **kwargs), policy=policy, retry_on=retry_on
            )

        return wrapper

    return decorator
