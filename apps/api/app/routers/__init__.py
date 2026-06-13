"""Routers HTTP de la API, agrupados por dominio."""

from __future__ import annotations

from app.routers.accounts import router as accounts_router
from app.routers.billing import router as billing_router
from app.routers.cycles import router as cycles_router
from app.routers.internal import router as internal_router
from app.routers.llm_providers import router as llm_providers_router
from app.routers.oauth import router as oauth_router
from app.routers.rules import router as rules_router

__all__ = [
    "accounts_router",
    "billing_router",
    "cycles_router",
    "internal_router",
    "llm_providers_router",
    "oauth_router",
    "rules_router",
]
