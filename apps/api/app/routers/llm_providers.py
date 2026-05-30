"""Endpoints CRUD para proveedores LLM (scoped por organización)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_org
from app.config import settings
from app.crypto import encrypt
from app.database import get_session
from app.models.llm_provider import LLMProvider
from app.models.organization import Organization
from app.schemas import LLMProviderCreate, LLMProviderOut, LLMProviderUpdate

router = APIRouter(prefix="/llm-providers", tags=["llm-providers"])


def _to_out(provider: LLMProvider) -> LLMProviderOut:
    out = LLMProviderOut.model_validate(provider)
    out.has_api_key = provider.encrypted_api_key is not None
    return out


async def _get_owned(
    provider_id: UUID, org: Organization, session: AsyncSession
) -> LLMProvider:
    provider = (
        await session.execute(
            select(LLMProvider).where(
                LLMProvider.id == provider_id, LLMProvider.org_id == org.id
            )
        )
    ).scalar_one_or_none()
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="llm_provider_not_found"
        )
    return provider


@router.get("", response_model=list[LLMProviderOut])
async def list_providers(
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> list[LLMProviderOut]:
    rows = await session.execute(
        select(LLMProvider)
        .where(LLMProvider.org_id == org.id)
        .order_by(LLMProvider.created_at)
    )
    return [_to_out(p) for p in rows.scalars()]


@router.post("", response_model=LLMProviderOut, status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: LLMProviderCreate,
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> LLMProviderOut:
    provider = LLMProvider(
        org_id=org.id,
        label=payload.label,
        type=payload.type,
        base_url=payload.base_url,
        encrypted_api_key=(
            encrypt({"api_key": payload.api_key}, settings.SECRET_KEY)
            if payload.api_key
            else None
        ),
        default_classification_model=payload.default_classification_model,
        default_generation_model=payload.default_generation_model,
    )
    session.add(provider)
    await session.commit()
    await session.refresh(provider)
    return _to_out(provider)


@router.get("/{provider_id}", response_model=LLMProviderOut)
async def get_provider(
    provider_id: UUID,
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> LLMProviderOut:
    return _to_out(await _get_owned(provider_id, org, session))


@router.patch("/{provider_id}", response_model=LLMProviderOut)
async def update_provider(
    provider_id: UUID,
    payload: LLMProviderUpdate,
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> LLMProviderOut:
    provider = await _get_owned(provider_id, org, session)
    data = payload.model_dump(exclude_unset=True)
    api_key = data.pop("api_key", None)
    if api_key:
        provider.encrypted_api_key = encrypt({"api_key": api_key}, settings.SECRET_KEY)
    for field, value in data.items():
        setattr(provider, field, value)
    await session.commit()
    await session.refresh(provider)
    return _to_out(provider)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: UUID,
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> None:
    provider = await _get_owned(provider_id, org, session)
    await session.delete(provider)
    await session.commit()
