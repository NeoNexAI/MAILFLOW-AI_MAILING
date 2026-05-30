"""Endpoints para reglas de clasificación de una cuenta.

Las reglas cuelgan de una email_account; el aislamiento de tenant se garantiza
comprobando que la cuenta pertenece a la organización del caller antes de
cualquier operación sobre sus reglas.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_org
from app.database import get_session
from app.models.email_account import EmailAccount
from app.models.organization import Organization
from app.models.rules import DomainRule, InternalDomain, KeywordRule
from app.schemas import (
    DomainRuleCreate,
    DomainRuleOut,
    InternalDomainCreate,
    InternalDomainOut,
    KeywordRuleCreate,
    KeywordRuleOut,
)

router = APIRouter(prefix="/accounts/{account_id}", tags=["rules"])


async def _assert_owned_account(
    account_id: UUID, org: Organization, session: AsyncSession
) -> None:
    """Lanza 404 si la cuenta no existe o no es de la organización del caller."""
    exists = (
        await session.execute(
            select(EmailAccount.id).where(
                EmailAccount.id == account_id, EmailAccount.org_id == org.id
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="account_not_found"
        )


# ── Domain rules ──────────────────────────────────────────────────────────────
@router.get("/domain-rules", response_model=list[DomainRuleOut])
async def list_domain_rules(
    account_id: UUID,
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> list[DomainRule]:
    await _assert_owned_account(account_id, org, session)
    rows = await session.execute(
        select(DomainRule)
        .where(DomainRule.account_id == account_id)
        .order_by(DomainRule.priority)
    )
    return list(rows.scalars())


@router.post(
    "/domain-rules", response_model=DomainRuleOut, status_code=status.HTTP_201_CREATED
)
async def create_domain_rule(
    account_id: UUID,
    payload: DomainRuleCreate,
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> DomainRule:
    await _assert_owned_account(account_id, org, session)
    rule = DomainRule(account_id=account_id, **payload.model_dump())
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


@router.delete("/domain-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_domain_rule(
    account_id: UUID,
    rule_id: UUID,
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> None:
    await _assert_owned_account(account_id, org, session)
    rule = (
        await session.execute(
            select(DomainRule).where(
                DomainRule.id == rule_id, DomainRule.account_id == account_id
            )
        )
    ).scalar_one_or_none()
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="rule_not_found"
        )
    await session.delete(rule)
    await session.commit()


# ── Keyword rules ─────────────────────────────────────────────────────────────
@router.get("/keyword-rules", response_model=list[KeywordRuleOut])
async def list_keyword_rules(
    account_id: UUID,
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> list[KeywordRule]:
    await _assert_owned_account(account_id, org, session)
    rows = await session.execute(
        select(KeywordRule)
        .where(KeywordRule.account_id == account_id)
        .order_by(KeywordRule.priority)
    )
    return list(rows.scalars())


@router.post(
    "/keyword-rules", response_model=KeywordRuleOut, status_code=status.HTTP_201_CREATED
)
async def create_keyword_rule(
    account_id: UUID,
    payload: KeywordRuleCreate,
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> KeywordRule:
    await _assert_owned_account(account_id, org, session)
    rule = KeywordRule(account_id=account_id, **payload.model_dump())
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


@router.delete("/keyword-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyword_rule(
    account_id: UUID,
    rule_id: UUID,
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> None:
    await _assert_owned_account(account_id, org, session)
    rule = (
        await session.execute(
            select(KeywordRule).where(
                KeywordRule.id == rule_id, KeywordRule.account_id == account_id
            )
        )
    ).scalar_one_or_none()
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="rule_not_found"
        )
    await session.delete(rule)
    await session.commit()


# ── Internal domains ──────────────────────────────────────────────────────────
@router.get("/internal-domains", response_model=list[InternalDomainOut])
async def list_internal_domains(
    account_id: UUID,
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> list[InternalDomain]:
    await _assert_owned_account(account_id, org, session)
    rows = await session.execute(
        select(InternalDomain).where(InternalDomain.account_id == account_id)
    )
    return list(rows.scalars())


@router.post(
    "/internal-domains",
    response_model=InternalDomainOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_internal_domain(
    account_id: UUID,
    payload: InternalDomainCreate,
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> InternalDomain:
    await _assert_owned_account(account_id, org, session)
    row = InternalDomain(account_id=account_id, domain=payload.domain)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


@router.delete("/internal-domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_internal_domain(
    account_id: UUID,
    domain_id: UUID,
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_session),
) -> None:
    await _assert_owned_account(account_id, org, session)
    row = (
        await session.execute(
            select(InternalDomain).where(
                InternalDomain.id == domain_id, InternalDomain.account_id == account_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="domain_not_found"
        )
    await session.delete(row)
    await session.commit()
