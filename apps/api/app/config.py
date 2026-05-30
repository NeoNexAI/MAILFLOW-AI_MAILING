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

    # Modo de autenticación:
    #   "single" — self-host: una única organización por defecto, sin tokens.
    #   "multi"  — SaaS: cada request debe traer una API key que resuelve su org.
    AUTH_MODE: str = "single"
    # API key usada en modo "single" (opcional). Si se define, las requests deben
    # enviarla; si se deja vacía, el self-host queda abierto (uso en LAN/local).
    SINGLE_TENANT_API_KEY: str = ""

    # OAuth2 (conectar Gmail / Microsoft 365 sin contraseña). Vacío = desactivado.
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    MICROSOFT_TENANT_ID: str = "common"
    # Base pública del API donde el proveedor redirige tras el consentimiento.
    # El callback completo es {OAUTH_REDIRECT_BASE}/oauth/{provider}/callback.
    OAUTH_REDIRECT_BASE: str = "http://localhost:8000"
    # A dónde enviar al usuario en el frontend tras conectar (éxito/fracaso).
    OAUTH_SUCCESS_REDIRECT: str = "http://localhost:3000/app/dashboard"

    @field_validator("AUTH_MODE", mode="before")
    @classmethod
    def _normalize_auth_mode(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Permite definir CORS_ORIGINS como CSV en la variable de entorno."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
