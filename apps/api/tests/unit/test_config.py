"""Tests para app.config.Settings — parsing de CORS_ORIGINS."""

from __future__ import annotations

_FAKE_KEY = "qdCa5nGhLjd8qY0CCaQP2dE000lbSYDmtPnhzAVeVgs="


def _make_settings(**env: str):
    """Construye Settings con variables de entorno controladas."""
    from app.config import Settings

    return Settings(SECRET_KEY=_FAKE_KEY, **env)


def test_cors_origins_default_is_local_frontend():
    settings = _make_settings()
    assert settings.CORS_ORIGINS == ["http://localhost:3000"]


def test_cors_origins_parses_csv_string():
    settings = _make_settings(
        CORS_ORIGINS="https://app.mailflow.ai, https://mailflow.ai"
    )
    assert settings.CORS_ORIGINS == ["https://app.mailflow.ai", "https://mailflow.ai"]


def test_cors_origins_csv_ignores_blanks():
    settings = _make_settings(CORS_ORIGINS="https://a.com,,  ,https://b.com")
    assert settings.CORS_ORIGINS == ["https://a.com", "https://b.com"]


def test_cors_origins_accepts_list():
    settings = _make_settings(CORS_ORIGINS=["https://only.com"])
    assert settings.CORS_ORIGINS == ["https://only.com"]
