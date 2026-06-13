"""Logging estructurado y correlación de eventos.

Configura el logging raíz en formato JSON (una línea por evento) para producción
o texto legible para desarrollo, según `settings.LOG_FORMAT`. Cada registro
arrastra los identificadores de correlación activos (request_id en la API,
cycle_id/account_id en el worker) vía `contextvars`, sin tener que pasarlos a
mano por cada llamada.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from typing import Any

from app.config import settings

# Identificadores de correlación. Se rellenan en los límites (middleware HTTP,
# inicio de un ciclo del worker) y los lee el formatter para anexarlos.
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
log_context_ctx: ContextVar[dict[str, Any]] = ContextVar("log_context", default={})

# Atributos estándar de LogRecord; todo lo demás en __dict__ es un "extra".
_RESERVED = set(logging.makeLogRecord({}).__dict__.keys()) | {
    "message",
    "asctime",
    "taskName",
}


def bind_log_context(**fields: Any) -> None:
    """Añade campos de correlación al contexto actual (p.ej. cycle_id)."""
    merged = {
        **log_context_ctx.get(),
        **{k: v for k, v in fields.items() if v is not None},
    }
    log_context_ctx.set(merged)


def clear_log_context() -> None:
    """Vacía el contexto de correlación (al terminar un ciclo/petición)."""
    log_context_ctx.set({})


class JsonFormatter(logging.Formatter):
    """Serializa cada LogRecord como una línea JSON con campos de correlación."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_ctx.get()
        if request_id:
            payload["request_id"] = request_id
        payload.update(log_context_ctx.get())

        # Cualquier `extra=` pasado al logger.
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


class ContextTextFormatter(logging.Formatter):
    """Formatter de texto para desarrollo, anexa correlación al final si existe."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        bits = []
        request_id = request_id_ctx.get()
        if request_id:
            bits.append(f"request_id={request_id}")
        for key, value in log_context_ctx.get().items():
            bits.append(f"{key}={value}")
        return f"{base} [{' '.join(bits)}]" if bits else base


def setup_logging() -> None:
    """Configura el handler raíz según settings. Idempotente."""
    formatter: logging.Formatter
    if settings.LOG_FORMAT.lower() == "json":
        formatter = JsonFormatter()
    else:
        formatter = ContextTextFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.LOG_LEVEL.upper())
