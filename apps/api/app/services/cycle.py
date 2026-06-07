"""CycleService — orquestación del loop de clasificación y borradores.

Este módulo contiene:
  - CycleResult: dataclass con resultado del ciclo
  - CycleService: orquestador principal
  - _process_one: procesa un email individual
  - _build_llm_client: construye LLMClient desde LLMProvider ORM model
  - _build_draft_bytes: convierte body text a email RFC2822 completo
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from uuid import UUID, uuid4

from mailflow_core.classification.llm_client import LLMClient, LLMConfig
from mailflow_core.classification.rule_engine import RuleEngine
from mailflow_core.email_parser import EmailParser
from mailflow_core.providers.base import EmailData
from mailflow_core.providers.imap_generic import ImapGenericProvider
from mailflow_core.resilience import RetryPolicy, retry_with_backoff
from mailflow_core.types import ClassificationResult, DraftRequest, ParsedEmail
from sqlalchemy.ext.asyncio import async_sessionmaker

from app import oauth
from app.config import settings
from app.crypto import decrypt
from app.models.email_account import EmailAccount
from app.models.llm_provider import LLMProvider
from app.models.organization import Organization
from app.quota import can_process_more
from app.repositories.account import AccountRepository
from app.repositories.cycle import CycleRepository

log = logging.getLogger("mailflow.cycle")


@dataclass
class CycleResult:
    cycle_id: UUID
    emails_processed: int
    drafts_saved: int
    errors: int


def _build_llm_client(
    llm_provider: LLMProvider | None,
    *,
    for_generation: bool,
) -> LLMClient | None:
    """Construye LLMClient con LLMConfig descifrado del provider.

    Args:
        llm_provider: modelo ORM LLMProvider (puede ser None).
        for_generation: True → default_generation_model;
                        False → default_classification_model.

    Returns:
        LLMClient configurado, o None si no hay provider activo.
    """
    if llm_provider is None or not llm_provider.is_active:
        return None

    api_key: str | None = None
    if llm_provider.encrypted_api_key:
        api_key = decrypt(llm_provider.encrypted_api_key, settings.SECRET_KEY)[
            "api_key"
        ]

    model_id = (
        llm_provider.default_generation_model
        if for_generation
        else llm_provider.default_classification_model
    )
    return LLMClient(
        LLMConfig(
            model_id=model_id,
            api_base=llm_provider.base_url,
            api_key=api_key,
        )
    )


def _build_draft_bytes(
    subject: str,
    from_email: str,
    to_email: str,
    body_text: str,
    in_reply_to: str | None = None,
) -> bytes:
    """Construye email RFC2822 mínimo listo para guardar como borrador IMAP.

    generate_draft() devuelve str (cuerpo del email).
    provider.save_draft() necesita bytes RFC2822 completos (headers + body).
    """
    msg = MIMEMultipart("alternative")
    reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    msg["Subject"] = reply_subject
    msg["From"] = from_email
    msg["To"] = to_email
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    return msg.as_bytes()


class CycleService:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._sf = session_factory

    async def run(self, account_id: UUID) -> CycleResult:
        cycle_id = uuid4()
        start = time.monotonic()
        stats: dict = {"emails": 0, "drafts": 0, "errors": 0, "last_error": None}

        # ── 0. Claim cycle — guard TOCTOU atómico ──────────────────────────
        now = datetime.now(tz=UTC)
        async with self._sf() as session:
            won = await AccountRepository(session).claim_cycle(account_id, now)
        if not won:
            log.info("Cycle for account %s already claimed, skipping", account_id)
            return CycleResult(
                cycle_id=cycle_id, emails_processed=0, drafts_saved=0, errors=0
            )

        # ── 1. Crear audit_log ──────────────────────────────────────────────
        async with self._sf() as session:
            await CycleRepository(session).create_audit_log(account_id, cycle_id)
            await session.commit()

        # ── 2. Cargar config (sesión breve, sin IMAP) ───────────────────────
        async with self._sf() as session:
            account, account_config, llm_provider = await AccountRepository(
                session
            ).get_full_config(account_id)
            await session.commit()

        # ── 2b. Cuota del plan: si la org superó su límite diario de emails,
        # se salta el ciclo (sin romper) y se registra el motivo. ────────────
        async with self._sf() as session:
            org = await session.get(Organization, account.org_id)
            plan_key = org.plan if org else None
            if not await can_process_more(session, account.org_id, plan_key):
                log.info(
                    "Account %s skipped: daily email quota reached (plan=%s)",
                    account_id,
                    plan_key,
                )
                await CycleRepository(session).finalize_audit_log(
                    cycle_id,
                    emails=0,
                    drafts=0,
                    errors=0,
                    error_detail="quota_reached",
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
                await session.commit()
                return CycleResult(cycle_id, 0, 0, 0)

        # ── 3. Construir herramientas de dominio ────────────────────────────
        # Cuentas OAuth (gmail/microsoft): refrescar access_token desde el refresh
        # token cifrado. Cuentas password: descifrar la contraseña IMAP.
        password: str | None = None
        access_token: str | None = None
        if account.provider_type in ("gmail", "microsoft") and account.encrypted_oauth:
            refresh_token = decrypt(account.encrypted_oauth, settings.SECRET_KEY)[
                "refresh_token"
            ]
            access_token = oauth.access_token_from_refresh(
                account.provider_type, refresh_token
            )
        elif account.encrypted_credentials:
            password = decrypt(account.encrypted_credentials, settings.SECRET_KEY)[
                "password"
            ]
        provider = ImapGenericProvider(
            host=account.imap_host,
            port=account.imap_port,
            username=account.username,
            password=password,
            use_ssl=account.use_ssl,
            access_token=access_token,
        )
        parser = EmailParser()
        # ADR-007: modelos distintos para clasificación y generación
        classify_client = _build_llm_client(llm_provider, for_generation=False)
        generate_client = _build_llm_client(llm_provider, for_generation=True)
        rule_engine = RuleEngine(account_config, llm_client=classify_client)

        # ── 4. Fetch + loop (sin sesión DB abierta durante IMAP) ────────────
        emails: list[EmailData] = []
        try:
            try:
                # IMAP connect+fetch con reintentos: tolera fallos transitorios
                # de red/servidor antes de abortar el ciclo.
                async def _connect_and_fetch() -> list[EmailData]:
                    provider.connect()
                    return provider.fetch_unprocessed_emails()

                emails = await retry_with_backoff(
                    _connect_and_fetch,
                    policy=RetryPolicy(max_attempts=3, base_delay=1.0),
                    on_retry=lambda attempt, exc: log.warning(
                        "IMAP fetch retry %d for account %s: %s",
                        attempt,
                        account_id,
                        exc,
                    ),
                )
            except Exception as exc:
                stats["last_error"] = str(exc)
                stats["errors"] += 1
                log.exception("IMAP fetch failed for account %s: %s", account_id, exc)

            for email_data in emails:
                try:
                    await _process_one(
                        email_data,
                        account,
                        cycle_id,
                        provider,
                        parser,
                        rule_engine,
                        generate_client,
                        stats,
                        self._sf,
                    )
                except Exception as exc:
                    stats["errors"] += 1
                    stats["last_error"] = str(exc)
                    log.exception("Error processing uid=%s: %s", email_data.uid, exc)
        finally:
            provider.disconnect()

        # ── 5. Finalizar audit_log ──────────────────────────────────────────
        duration_ms = int((time.monotonic() - start) * 1000)
        async with self._sf() as session:
            await CycleRepository(session).finalize_audit_log(
                cycle_id,
                emails=stats["emails"],
                drafts=stats["drafts"],
                errors=stats["errors"],
                error_detail=stats["last_error"],
                duration_ms=duration_ms,
            )
            await session.commit()

        return CycleResult(cycle_id, stats["emails"], stats["drafts"], stats["errors"])


async def _process_one(
    email_data: EmailData,
    account: EmailAccount,
    cycle_id: UUID,
    provider: ImapGenericProvider,
    parser: EmailParser,
    rule_engine: RuleEngine,
    generate_client: LLMClient | None,
    stats: dict,
    sf: async_sessionmaker,
) -> None:
    """Procesa un email individual. Excepciones propagadas — caller las captura."""

    # a. Parse → ParsedEmail
    parsed: ParsedEmail = parser.parse(email_data)

    # b. Thread-inheritance check
    thread_folder: str | None = None
    if parsed.in_reply_to:
        async with sf() as session:
            thread_folder = await CycleRepository(session).find_thread_folder(
                account.id, parsed.in_reply_to
            )

    # c. Clasificar
    if thread_folder:
        result = ClassificationResult(
            label=thread_folder, confidence=0.95, method="thread"
        )
    else:
        result = rule_engine.classify(parsed)

    destination = (
        result.label if result.label != "unclassified" else account.unclassified_folder
    )

    # d. INVARIANTE: mark ANTES de move. Tras move, el UID no existe en INBOX.
    provider.mark_as_processed(email_data.uid)
    provider.move_email(email_data.uid, destination)

    # e. Generar borrador (solo emails no-internos y clasificados)
    draft_saved = False
    if (
        result.method != "domain_internal"
        and result.label != "unclassified"
        and generate_client
    ):
        draft_request = DraftRequest(
            in_reply_to_uid=str(email_data.uid),
            # _drafts_folder es privado — tech debt Phase 2a (ver spec §15)
            folder=provider._drafts_folder,
            subject=parsed.subject_normalized,
            body_text=parsed.body_text,
            body_html=parsed.body_html or None,
            classification=result,
        )

        # La generación con LLM es la llamada externa más inestable: reintentar
        # con backoff evita perder el borrador por un fallo transitorio. El email
        # ya está clasificado y movido, así que un fallo final solo omite el draft.
        async def _generate() -> str:
            return generate_client.generate_draft(parsed, draft_request)

        try:
            draft_text = await retry_with_backoff(
                _generate,
                policy=RetryPolicy(max_attempts=3, base_delay=0.5),
                on_retry=lambda attempt, exc: log.warning(
                    "LLM draft retry %d for uid=%s: %s", attempt, email_data.uid, exc
                ),
            )
        except Exception as exc:
            log.warning(
                "LLM draft generation failed for uid=%s: %s", email_data.uid, exc
            )
            draft_text = ""
        if draft_text:
            draft_bytes = _build_draft_bytes(
                subject=parsed.subject_normalized,
                from_email=account.username,
                to_email=email_data.from_email,
                body_text=draft_text,
                in_reply_to=email_data.message_id,
            )
            draft_saved = provider.save_draft(draft_bytes)

    # f. Persistir en DB (commit por email → idempotencia ON CONFLICT DO NOTHING)
    async with sf() as session:
        await CycleRepository(session).insert_processed(
            account_id=account.id,
            uid=email_data.uid,
            folder=account.inbox_folder,
            # _uidvalidity es privado — tech debt Phase 2a (ver spec §15)
            uidvalidity=provider._uidvalidity.get(account.inbox_folder, 0),
            message_id=email_data.message_id,
            from_email=email_data.from_email,
            subject=email_data.subject,
            destination_folder=destination,
            method=result.method,
            confidence=result.confidence,
            draft_saved=draft_saved,
            cycle_id=cycle_id,
        )
        await session.commit()

    stats["emails"] += 1
    if draft_saved:
        stats["drafts"] += 1
