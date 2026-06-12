"""Modelo StripeEvent — registro de webhooks de Stripe ya procesados.

Stripe reintenta los webhooks; guardar el `id` del evento permite ignorar
duplicados de forma idempotente (insert ON CONFLICT DO NOTHING).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StripeEvent(Base):
    __tablename__ = "stripe_events"

    # El id del evento de Stripe (evt_...) es la clave primaria.
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
