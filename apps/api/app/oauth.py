"""OAuth2 para conectar buzones Gmail / Microsoft 365 sin contraseña.

Gmail y M365 exponen IMAP con XOAUTH2, así que solo necesitamos obtener y
refrescar un access_token; el acceso al buzón lo hace ImapGenericProvider.

Flujo (Authorization Code):
  1. authorize_url(provider, state) → URL de consentimiento.
  2. el proveedor redirige a REDIRECT_URI con ?code=...&state=...
  3. exchange_code(provider, code) → {refresh_token, email}.
  4. en cada ciclo, access_token_from_refresh(provider, refresh_token).

Todo es config-driven (CLIENT_ID/SECRET/REDIRECT_URI). Si falta config, se lanza
OAuthNotConfigured para que las rutas devuelvan un 400 claro.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import settings

# Endpoints IMAP por proveedor.
IMAP_ENDPOINTS = {
    "gmail": ("imap.gmail.com", 993),
    "microsoft": ("outlook.office365.com", 993),
}

# Scopes necesarios para acceso IMAP + refresh token offline.
_GOOGLE_SCOPES = ["https://mail.google.com/"]
_MS_SCOPES = ["https://outlook.office365.com/IMAP.AccessAsUser.All", "offline_access"]

_GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"


class OAuthError(Exception):
    """Fallo genérico de OAuth."""


class OAuthNotConfigured(OAuthError):
    """El proveedor OAuth no tiene CLIENT_ID/SECRET configurados."""


@dataclass(frozen=True)
class OAuthResult:
    """Resultado del intercambio de code: refresh token + email del buzón."""

    refresh_token: str
    email: str


def is_supported(provider: str) -> bool:
    return provider in IMAP_ENDPOINTS


def imap_endpoint(provider: str) -> tuple[str, int]:
    if provider not in IMAP_ENDPOINTS:
        raise OAuthError(f"unsupported provider: {provider}")
    return IMAP_ENDPOINTS[provider]


def _google_config() -> tuple[str, str]:
    cid = settings.GOOGLE_CLIENT_ID
    secret = settings.GOOGLE_CLIENT_SECRET
    if not cid or not secret:
        raise OAuthNotConfigured("GOOGLE_CLIENT_ID/SECRET not set")
    return cid, secret


def _ms_config() -> tuple[str, str, str]:
    cid = settings.MICROSOFT_CLIENT_ID
    secret = settings.MICROSOFT_CLIENT_SECRET
    if not cid or not secret:
        raise OAuthNotConfigured("MICROSOFT_CLIENT_ID/SECRET not set")
    return cid, secret, settings.MICROSOFT_TENANT_ID or "common"


def authorize_url(provider: str, state: str) -> str:
    """Construye la URL de consentimiento del proveedor."""
    redirect = f"{settings.OAUTH_REDIRECT_BASE}/oauth/{provider}/callback"
    if provider == "gmail":
        cid, _ = _google_config()
        from urllib.parse import urlencode

        params = {
            "client_id": cid,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": " ".join(_GOOGLE_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{_GOOGLE_AUTH}?{urlencode(params)}"
    if provider == "microsoft":
        cid, secret, tenant = _ms_config()
        import msal

        app = msal.ConfidentialClientApplication(
            cid,
            authority=f"https://login.microsoftonline.com/{tenant}",
            client_credential=secret,
        )
        return app.get_authorization_request_url(
            _MS_SCOPES, state=state, redirect_uri=redirect
        )
    raise OAuthError(f"unsupported provider: {provider}")


def exchange_code(provider: str, code: str) -> OAuthResult:
    """Canjea el authorization code por un refresh token + email del buzón."""
    redirect = f"{settings.OAUTH_REDIRECT_BASE}/oauth/{provider}/callback"
    if provider == "gmail":
        return _google_exchange(code, redirect)
    if provider == "microsoft":
        return _ms_exchange(code, redirect)
    raise OAuthError(f"unsupported provider: {provider}")


def access_token_from_refresh(provider: str, refresh_token: str) -> str:
    """Obtiene un access_token fresco a partir del refresh token almacenado."""
    if provider == "gmail":
        return _google_refresh(refresh_token)
    if provider == "microsoft":
        return _ms_refresh(refresh_token)
    raise OAuthError(f"unsupported provider: {provider}")


# ── Google ────────────────────────────────────────────────────────────────────
def _google_exchange(code: str, redirect: str) -> OAuthResult:
    import json
    import urllib.request

    cid, secret = _google_config()
    data = _post_form(
        _GOOGLE_TOKEN,
        {
            "code": code,
            "client_id": cid,
            "client_secret": secret,
            "redirect_uri": redirect,
            "grant_type": "authorization_code",
        },
    )
    refresh = data.get("refresh_token")
    if not refresh:
        raise OAuthError("Google did not return a refresh_token")
    email = _google_email_from_id_token(data.get("id_token", ""))
    # Fallback: si no hay id_token, usar el access token para userinfo.
    if not email:
        with urllib.request.urlopen(  # noqa: S310 — URL fija de Google
            urllib.request.Request(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {data['access_token']}"},
            )
        ) as resp:
            email = json.loads(resp.read()).get("email", "")
    return OAuthResult(refresh_token=refresh, email=email)


def _google_refresh(refresh_token: str) -> str:
    cid, secret = _google_config()
    data = _post_form(
        _GOOGLE_TOKEN,
        {
            "refresh_token": refresh_token,
            "client_id": cid,
            "client_secret": secret,
            "grant_type": "refresh_token",
        },
    )
    token = data.get("access_token")
    if not token:
        raise OAuthError("Google refresh failed")
    return token


def _google_email_from_id_token(id_token: str) -> str:
    if not id_token or id_token.count(".") != 2:
        return ""
    import base64
    import json

    payload = id_token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return claims.get("email", "")
    except Exception:
        return ""


# ── Microsoft ─────────────────────────────────────────────────────────────────
def _ms_app():
    import msal

    cid, secret, tenant = _ms_config()
    return msal.ConfidentialClientApplication(
        cid,
        authority=f"https://login.microsoftonline.com/{tenant}",
        client_credential=secret,
    )


def _ms_exchange(code: str, redirect: str) -> OAuthResult:
    app = _ms_app()
    result = app.acquire_token_by_authorization_code(
        code, scopes=_MS_SCOPES, redirect_uri=redirect
    )
    if "refresh_token" not in result:
        raise OAuthError(
            result.get("error_description", "Microsoft token exchange failed")
        )
    claims = result.get("id_token_claims", {})
    email = claims.get("preferred_username") or claims.get("email", "")
    return OAuthResult(refresh_token=result["refresh_token"], email=email)


def _ms_refresh(refresh_token: str) -> str:
    app = _ms_app()
    result = app.acquire_token_by_refresh_token(refresh_token, scopes=_MS_SCOPES)
    token = result.get("access_token")
    if not token:
        raise OAuthError(result.get("error_description", "Microsoft refresh failed"))
    return token


# ── helpers ───────────────────────────────────────────────────────────────────
def _post_form(url: str, fields: dict[str, str]) -> dict:
    """POST application/x-www-form-urlencoded usando stdlib (sin httpx en runtime)."""
    import json
    import urllib.parse
    import urllib.request

    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(  # noqa: S310 — URLs de proveedores OAuth conocidas
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:  # noqa: S310
        return json.loads(resp.read())
