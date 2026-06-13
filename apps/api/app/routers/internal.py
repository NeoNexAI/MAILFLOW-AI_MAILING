"""Endpoints internos (server-to-server), no expuestos al público.

Los usa el servidor web (Better Auth) para aprovisionar una organización cuando
un usuario se registra: crea la org en la tabla `organizations` del API y emite
su API key. La confianza viene de un secreto compartido `INTERNAL_API_SECRET`
(header `X-Internal-Secret`), nunca de la sesión del usuario.

NUNCA debe ser accesible desde internet: en el reverse proxy / Coolify hay que
bloquear `/internal/*` desde fuera; aquí además exige el secreto.
"""

from __future__ import annotations

import re
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import generate_api_key
from app.config import settings
from app.database import get_session
from app.models.organization import Organization

router = APIRouter(prefix="/internal", tags=["internal"])


async def require_internal_secret(
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
) -> None:
    """Guard: exige el secreto compartido. 501 si no está configurado, 403 si no coincide."""
    if not settings.INTERNAL_API_SECRET:
        raise HTTPException(status_code=501, detail="internal_api_disabled")
    if not x_internal_secret or not secrets.compare_digest(
        x_internal_secret, settings.INTERNAL_API_SECRET
    ):
        raise HTTPException(status_code=403, detail="forbidden")


class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=100)


class OrgCreated(BaseModel):
    org_id: str
    slug: str
    # La API key en claro viaja UNA sola vez (server-to-server); luego solo se
    # guarda su hash. El web la cifra en el metadata de la org de Better Auth.
    api_key: str


def _slugify(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return s[:80] or "org"


@router.post(
    "/orgs",
    response_model=OrgCreated,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_internal_secret)],
)
async def create_org(
    payload: OrgCreate,
    session: AsyncSession = Depends(get_session),
) -> OrgCreated:
    """Crea una organización y emite su API key (idempotente por slug)."""
    base_slug = _slugify(payload.slug or payload.name)
    slug = base_slug
    # Garantiza unicidad del slug añadiendo un sufijo corto si choca.
    for _ in range(5):
        exists = (
            await session.execute(
                select(Organization.id).where(Organization.slug == slug)
            )
        ).scalar_one_or_none()
        if exists is None:
            break
        slug = f"{base_slug}-{secrets.token_hex(3)}"

    raw_key, key_hash = generate_api_key()
    org = Organization(name=payload.name, slug=slug, api_key_hash=key_hash)
    session.add(org)
    await session.commit()
    await session.refresh(org)
    return OrgCreated(org_id=str(org.id), slug=org.slug, api_key=raw_key)
