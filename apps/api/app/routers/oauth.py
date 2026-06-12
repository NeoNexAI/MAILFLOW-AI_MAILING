"""Rutas OAuth2 para conectar buzones Gmail / Microsoft 365.

  GET /oauth/{provider}/authorize  → URL de consentimiento (scoped por org).
  GET /oauth/{provider}/callback    → canjea el code y crea/actualiza la cuenta.

El `state` lleva el org_id firmado con HMAC(SECRET_KEY) para que el callback
(que no pasa por require_org) sepa a qué organización pertenece, sin confiar en
datos no verificados del navegador.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import oauth
from app.auth import require_org
from app.config import settings
from app.crypto import encrypt
from app.database import get_session
from app.models.email_account import EmailAccount
from app.models.organization import Organization

logger = logging.getLogger("mailflow.api")

router = APIRouter(prefix="/oauth", tags=["oauth"])

# Tiempo de vida del state OAuth (segundos). Limita la ventana de un posible
# login-CSRF: un state robado/replicado caduca pronto.
STATE_TTL_SECONDS = 600


# La firma HMAC-SHA256 siempre mide 32 bytes; se anexa al final del payload y se
# trocea por longitud fija. (No usar un separador de byte: la firma binaria puede
# contener cualquier byte, incluido el del separador → split ambiguo.)
_SIG_LEN = 32


def _sign_state(org_id: str) -> str:
    """Firma {org, nonce, ts} con HMAC-SHA256 → token base64url verificable.

    El `nonce` hace cada state único y el `ts` permite caducarlo.
    """
    payload = json.dumps(
        {"org": org_id, "nonce": secrets.token_urlsafe(8), "ts": int(time.time())}
    ).encode()
    sig = hmac.new(settings.SECRET_KEY.encode(), payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(payload + sig).decode()


def _verify_state(state: str) -> str:
    """Valida firma y caducidad del state; devuelve el org_id. Lanza si inválido."""
    try:
        raw = base64.urlsafe_b64decode(state.encode())
        payload, sig = raw[:-_SIG_LEN], raw[-_SIG_LEN:]
        if not payload:
            raise ValueError("empty payload")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="invalid_state") from exc
    expected = hmac.new(settings.SECRET_KEY.encode(), payload, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=400, detail="invalid_state")
    data = json.loads(payload)
    if int(time.time()) - int(data.get("ts", 0)) > STATE_TTL_SECONDS:
        raise HTTPException(status_code=400, detail="state_expired")
    return data["org"]


@router.get("/{provider}/authorize")
async def authorize(
    provider: str,
    org: Organization = Depends(require_org),
) -> dict[str, str]:
    """Devuelve la URL de consentimiento del proveedor para esta organización."""
    if not oauth.is_supported(provider):
        raise HTTPException(status_code=404, detail="unsupported_provider")
    try:
        url = oauth.authorize_url(provider, _sign_state(str(org.id)))
    except oauth.OAuthNotConfigured as exc:
        raise HTTPException(
            status_code=400, detail=f"oauth_not_configured: {exc}"
        ) from exc
    return {"authorize_url": url}


@router.get("/{provider}/callback")
async def callback(
    provider: str,
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """Callback del proveedor: canjea el code y conecta el buzón.

    Redirige al frontend (OAUTH_SUCCESS_REDIRECT) con ?connected o ?error.
    """
    success = settings.OAUTH_SUCCESS_REDIRECT
    if error:
        return RedirectResponse(f"{success}?error={error}", status_code=302)
    if not code or not state or not oauth.is_supported(provider):
        return RedirectResponse(f"{success}?error=invalid_request", status_code=302)

    org_id = UUID(_verify_state(state))
    try:
        # exchange_code hace I/O HTTP síncrono → a un hilo.
        result = await asyncio.to_thread(oauth.exchange_code, provider, code)
    except oauth.OAuthError as exc:
        logger.warning("oauth exchange failed (%s): %s", provider, exc)
        return RedirectResponse(f"{success}?error=oauth_failed", status_code=302)

    host, port = oauth.imap_endpoint(provider)

    # Upsert por (org, username, provider): reconectar no duplica la cuenta.
    existing = (
        await session.execute(
            select(EmailAccount).where(
                EmailAccount.org_id == org_id,
                EmailAccount.username == result.email,
                EmailAccount.provider_type == provider,
            )
        )
    ).scalar_one_or_none()

    enc = encrypt({"refresh_token": result.refresh_token}, settings.SECRET_KEY)
    if existing:
        existing.encrypted_oauth = enc
        existing.is_active = True
    else:
        session.add(
            EmailAccount(
                org_id=org_id,
                provider_type=provider,
                imap_host=host,
                imap_port=port,
                use_ssl=True,
                username=result.email,
                encrypted_oauth=enc,
            )
        )
    await session.commit()
    return RedirectResponse(
        f"{success}?connected={provider}", status_code=status.HTTP_302_FOUND
    )
