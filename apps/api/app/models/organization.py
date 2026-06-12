"""Modelo Organization — tenant raíz del sistema."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    plan: Mapped[str] = mapped_column(String(20), default="free")
    # Asientos contratados (plan Team se factura por asiento, mínimo 3).
    # 1 para free/pro. Lo fija el webhook de Stripe tras el checkout.
    seats: Mapped[int] = mapped_column(Integer, default=1)
    # SHA-256 hex of the org's API key (multi-tenant auth). Null until issued.
    api_key_hash: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True
    )
    # Stripe billing linkage (SaaS). Null hasta que la org pasa por checkout.
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
