"""Endpoints CRUD para cuentas de email (scoped por organización)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_org
from app.config import settings
from app.crypto import encrypt
from app.database import get_session
from app.models.email_account import EmailAccount
from app.models.organization import Organization
from app.quota import can_add_account
from app.schemas import EmailAccountCreate, EmailAccountOut, EmailAccountUpdate

router = APIRouter(prefix="/accounts", tags=["accounts"])


async def _get_owned_account(
    account_id: UUID, org: Organization, session: AsyncSession
) -> EmailAccount:
    """Carga una cuenta garantizando que pertenece a la organización del caller."""
    account = (
        await session.execute(
            select(EmailAccount).where(
                EmailAccount.id == account_id,
                EmailAccount.org_id == org.id,
            )
        )
    ).scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="account_not_found"
        )
    return account


@router.get("", response_model=list[EmailAccountOut])
async def list_accounts(
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> list[EmailAccount]:
    rows = await session.execute(
        select(EmailAccount)
        .where(EmailAccount.org_id == org.id)
        .order_by(EmailAccount.created_at)
    )
    return list(rows.scalars())


@router.post("", response_model=EmailAccountOut, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: EmailAccountCreate,
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> EmailAccount:
    # Cuota del plan: el plan free limita el número de cuentas conectadas.
    if not await can_add_account(session, org.id, org.plan):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="account_limit_reached",
        )
    account = EmailAccount(
        org_id=org.id,
        provider_type=payload.provider_type,
        imap_host=payload.imap_host,
        imap_port=payload.imap_port,
        use_ssl=payload.use_ssl,
        username=payload.username,
        encrypted_credentials=encrypt(
            {"password": payload.password}, settings.SECRET_KEY
        ),
        inbox_folder=payload.inbox_folder,
        unclassified_folder=payload.unclassified_folder,
        drafts_folder=payload.drafts_folder,
        interval_minutes=payload.interval_minutes,
        llm_provider_id=payload.llm_provider_id,
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


@router.get("/{account_id}", response_model=EmailAccountOut)
async def get_account(
    account_id: UUID,
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> EmailAccount:
    return await _get_owned_account(account_id, org, session)


@router.patch("/{account_id}", response_model=EmailAccountOut)
async def update_account(
    account_id: UUID,
    payload: EmailAccountUpdate,
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> EmailAccount:
    account = await _get_owned_account(account_id, org, session)
    data = payload.model_dump(exclude_unset=True)
    password = data.pop("password", None)
    if password:
        account.encrypted_credentials = encrypt(
            {"password": password}, settings.SECRET_KEY
        )
    for field, value in data.items():
        setattr(account, field, value)
    await session.commit()
    await session.refresh(account)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: UUID,
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> None:
    account = await _get_owned_account(account_id, org, session)
    await session.delete(account)
    await session.commit()
