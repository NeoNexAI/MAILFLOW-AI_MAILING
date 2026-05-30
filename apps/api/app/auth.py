"""Autenticación y resolución de organización (tenant) por request.

Soporta dos modos (config.AUTH_MODE), habilitando OSS self-host y SaaS con el
mismo código:

  - "single": self-host. Existe una única organización (slug "default"), que se
    crea bajo demanda. Si SINGLE_TENANT_API_KEY está definida, se exige en la
    cabecera; si está vacía, el acceso es abierto (uso local/LAN).
  - "multi": SaaS. Cada request debe enviar una API key (cabecera
    `X-API-Key` o `Authorization: Bearer <key>`) que se hashea y resuelve a una
    organización concreta vía organizations.api_key_hash.

La API key nunca se almacena en claro: solo su SHA-256.
"""

from __future__ import annotations

import hashlib
import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models.organization import Organization

DEFAULT_ORG_SLUG = "default"
API_KEY_PREFIX = "mf_"


def hash_api_key(raw_key: str) -> str:
    """SHA-256 hex de una API key. Determinista para poder buscar por igualdad."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """Genera (clave_en_claro, hash). La clave en claro se muestra una sola vez."""
    raw = API_KEY_PREFIX + secrets.token_urlsafe(32)
    return raw, hash_api_key(raw)


def _extract_key(
    x_api_key: str | None,
    authorization: str | None,
) -> str | None:
    """Lee la API key de X-API-Key o de Authorization: Bearer <key>."""
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


async def _get_or_create_default_org(session: AsyncSession) -> Organization:
    """Devuelve la organización por defecto (self-host), creándola si no existe."""
    org = (
        await session.execute(
            select(Organization).where(Organization.slug == DEFAULT_ORG_SLUG)
        )
    ).scalar_one_or_none()
    if org is None:
        org = Organization(name="Default", slug=DEFAULT_ORG_SLUG, plan="free")
        session.add(org)
        await session.commit()
        await session.refresh(org)
    return org


async def require_org(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> Organization:
    """Dependency de FastAPI: resuelve la organización del request.

    Lanza 401 si la autenticación falla. Devuelve la `Organization` para que los
    handlers filtren por `org.id` (aislamiento de tenant).
    """
    provided = _extract_key(x_api_key, authorization)

    if settings.AUTH_MODE == "multi":
        if not provided:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key requerida",
                headers={"WWW-Authenticate": "Bearer"},
            )
        org = (
            await session.execute(
                select(Organization).where(
                    Organization.api_key_hash == hash_api_key(provided)
                )
            )
        ).scalar_one_or_none()
        if org is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key inválida",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return org

    # Modo "single" (self-host).
    expected = settings.SINGLE_TENANT_API_KEY
    if expected and not secrets.compare_digest(provided or "", expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _get_or_create_default_org(session)
