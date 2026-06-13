"""Tests del logging estructurado y la correlación por contextvars."""

from __future__ import annotations

import json
import logging
import os

os.environ.setdefault("SECRET_KEY", "qdCa5nGhLjd8qY0CCaQP2dE000lbSYDmtPnhzAVeVgs=")


def _record(**kwargs) -> logging.LogRecord:
    return logging.makeLogRecord(
        {"name": "test", "levelname": "INFO", "levelno": logging.INFO, **kwargs}
    )


def test_json_formatter_emits_parseable_line():
    from app.logging_config import JsonFormatter

    out = JsonFormatter().format(_record(msg="hola %s", args=("mundo",)))
    payload = json.loads(out)
    assert payload["message"] == "hola mundo"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test"
    assert "ts" in payload


def test_json_formatter_includes_request_id_and_context():
    from app.logging_config import (
        JsonFormatter,
        bind_log_context,
        clear_log_context,
        request_id_ctx,
    )

    token = request_id_ctx.set("req-123")
    bind_log_context(cycle_id="cyc-9", account_id="acc-1")
    try:
        payload = json.loads(JsonFormatter().format(_record(msg="x")))
    finally:
        request_id_ctx.reset(token)
        clear_log_context()

    assert payload["request_id"] == "req-123"
    assert payload["cycle_id"] == "cyc-9"
    assert payload["account_id"] == "acc-1"


def test_json_formatter_includes_extra_fields():
    from app.logging_config import JsonFormatter

    payload = json.loads(
        JsonFormatter().format(_record(msg="m", event="cycle_completed", errors=2))
    )
    assert payload["event"] == "cycle_completed"
    assert payload["errors"] == 2


def test_json_formatter_serializes_exception():
    from app.logging_config import JsonFormatter

    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _record(msg="failed", exc_info=sys.exc_info())
    payload = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in payload["exc_info"]


def test_bind_log_context_ignores_none_and_merges():
    from app.logging_config import bind_log_context, clear_log_context, log_context_ctx

    clear_log_context()
    bind_log_context(a="1", skip=None)
    bind_log_context(b="2")
    try:
        ctx = log_context_ctx.get()
        assert ctx == {"a": "1", "b": "2"}
    finally:
        clear_log_context()


def test_setup_logging_json_then_text(monkeypatch):
    from app import logging_config
    from app.config import settings

    monkeypatch.setattr(settings, "LOG_FORMAT", "json")
    monkeypatch.setattr(settings, "LOG_LEVEL", "WARNING")
    logging_config.setup_logging()
    root = logging.getLogger()
    assert isinstance(root.handlers[0].formatter, logging_config.JsonFormatter)
    assert root.level == logging.WARNING

    monkeypatch.setattr(settings, "LOG_FORMAT", "text")
    monkeypatch.setattr(settings, "LOG_LEVEL", "INFO")
    logging_config.setup_logging()
    assert isinstance(
        logging.getLogger().handlers[0].formatter,
        logging_config.ContextTextFormatter,
    )
