"""Esquemas Pydantic (DTOs) para la API HTTP.

Separan el contrato HTTP de los modelos SQLAlchemy. Las credenciales/secretos
(passwords IMAP, API keys de LLM) solo se aceptan en la entrada (write-only) y
NUNCA se devuelven en las respuestas.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Email accounts ────────────────────────────────────────────────────────────
class EmailAccountCreate(BaseModel):
    imap_host: str = Field(min_length=1, max_length=255)
    imap_port: int = 993
    use_ssl: bool = True
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, repr=False)  # write-only, se cifra
    inbox_folder: str = "INBOX"
    unclassified_folder: str = "Sin_Clasificar"
    drafts_folder: str = "Drafts"
    interval_minutes: int = Field(default=5, ge=1, le=1440)
    provider_type: str = "imap"
    llm_provider_id: UUID | None = None


class EmailAccountUpdate(BaseModel):
    imap_host: str | None = Field(default=None, max_length=255)
    imap_port: int | None = None
    use_ssl: bool | None = None
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, repr=False)
    inbox_folder: str | None = None
    unclassified_folder: str | None = None
    drafts_folder: str | None = None
    interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    is_active: bool | None = None
    llm_provider_id: UUID | None = None


class EmailAccountOut(ORMModel):
    id: UUID
    org_id: UUID
    provider_type: str
    imap_host: str
    imap_port: int
    use_ssl: bool
    username: str
    inbox_folder: str
    unclassified_folder: str
    drafts_folder: str
    interval_minutes: int
    is_active: bool
    last_cycle_at: datetime | None
    llm_provider_id: UUID | None
    created_at: datetime


# ── LLM providers ─────────────────────────────────────────────────────────────
class LLMProviderCreate(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    type: str = Field(min_length=1, max_length=50)
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str | None = Field(default=None, repr=False)  # write-only, se cifra
    default_classification_model: str = Field(min_length=1, max_length=200)
    default_generation_model: str = Field(min_length=1, max_length=200)


class LLMProviderUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=100)
    type: str | None = Field(default=None, max_length=50)
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, repr=False)
    default_classification_model: str | None = Field(default=None, max_length=200)
    default_generation_model: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None


class LLMProviderOut(ORMModel):
    id: UUID
    org_id: UUID
    label: str
    type: str
    base_url: str
    default_classification_model: str
    default_generation_model: str
    is_active: bool
    has_api_key: bool = False
    created_at: datetime


# ── Rules ─────────────────────────────────────────────────────────────────────
class DomainRuleCreate(BaseModel):
    domain: str = Field(min_length=1, max_length=255)
    label: str = Field(min_length=1, max_length=255)
    rule_id: str = Field(min_length=1, max_length=100)
    priority: int = 0


class DomainRuleOut(ORMModel):
    id: UUID
    account_id: UUID
    domain: str
    label: str
    rule_id: str
    priority: int


class KeywordRuleCreate(BaseModel):
    keywords: list[str] = Field(min_length=1)
    label: str = Field(min_length=1, max_length=255)
    rule_id: str = Field(min_length=1, max_length=100)
    match_all: bool = False
    priority: int = 0


class KeywordRuleOut(ORMModel):
    id: UUID
    account_id: UUID
    keywords: list[str]
    label: str
    rule_id: str
    match_all: bool
    priority: int


class InternalDomainCreate(BaseModel):
    domain: str = Field(min_length=1, max_length=255)


class InternalDomainOut(ORMModel):
    id: UUID
    account_id: UUID
    domain: str


# ── Cycles / audit log ──────────────────────────────────────────────────────--
class CycleOut(ORMModel):
    id: UUID
    account_id: UUID
    cycle_id: UUID
    emails_processed: int
    drafts_saved: int
    error_count: int
    error_detail: str | None
    duration_ms: int | None
    created_at: datetime
    finalized_at: datetime | None


class CycleEnqueuedOut(BaseModel):
    account_id: UUID
    enqueued: bool
    job_id: str | None = None
