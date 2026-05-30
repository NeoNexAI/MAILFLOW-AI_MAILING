"""Configuración de la aplicación vía variables de entorno."""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://mailflow:mailflow@localhost:5432/mailflow"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: (
        str  # Must be set via environment variable — Fernet key (44-char base64)
    )
    # Orígenes permitidos para CORS. Coma-separados en la variable de entorno
    # CORS_ORIGINS (p.ej. "https://app.mailflow.ai,https://mailflow.ai").
    # Por defecto solo el frontend local de desarrollo.
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Permite definir CORS_ORIGINS como CSV en la variable de entorno."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
