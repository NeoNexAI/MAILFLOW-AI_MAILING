"""Tests de los helpers OAuth y la firma del state (sin red ni DB)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SECRET_KEY", "qdCa5nGhLjd8qY0CCaQP2dE000lbSYDmtPnhzAVeVgs=")


# ── state signing (router) ────────────────────────────────────────────────────
def test_state_sign_verify_roundtrip():
    from app.routers.oauth import _sign_state, _verify_state

    state = _sign_state("org-123")
    assert _verify_state(state) == "org-123"


def test_state_tamper_is_rejected():
    from fastapi import HTTPException

    from app.routers.oauth import _sign_state, _verify_state

    state = _sign_state("org-123")
    tampered = state[:-2] + ("AA" if not state.endswith("AA") else "BB")
    with pytest.raises(HTTPException):
        _verify_state(tampered)


def test_garbage_state_is_rejected():
    from fastapi import HTTPException

    from app.routers.oauth import _verify_state

    with pytest.raises(HTTPException):
        _verify_state("not-a-valid-state")


# ── provider support ──────────────────────────────────────────────────────────
def test_supported_providers_and_endpoints():
    from app import oauth

    assert oauth.is_supported("gmail")
    assert oauth.is_supported("microsoft")
    assert not oauth.is_supported("imap")
    assert oauth.imap_endpoint("gmail") == ("imap.gmail.com", 993)
    assert oauth.imap_endpoint("microsoft") == ("outlook.office365.com", 993)


def test_authorize_url_not_configured_raises():
    from app import oauth
    from app.config import settings

    # Sin CLIENT_ID/SECRET → OAuthNotConfigured.
    orig = (settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET)
    settings.GOOGLE_CLIENT_ID = ""
    settings.GOOGLE_CLIENT_SECRET = ""
    try:
        with pytest.raises(oauth.OAuthNotConfigured):
            oauth.authorize_url("gmail", "state123")
    finally:
        settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET = orig


def test_google_authorize_url_includes_params(monkeypatch):
    from app import oauth
    from app.config import settings

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "gid")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "gsecret")
    monkeypatch.setattr(settings, "OAUTH_REDIRECT_BASE", "https://api.example.com")

    url = oauth.authorize_url("gmail", "state-xyz")
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=gid" in url
    assert "state=state-xyz" in url
    assert "access_type=offline" in url
    assert "mail.google.com" in url
    assert "oauth%2Fgmail%2Fcallback" in url


def test_email_from_id_token_decodes_claims():
    import base64
    import json

    from app.oauth import _google_email_from_id_token

    payload = (
        base64.urlsafe_b64encode(json.dumps({"email": "me@gmail.com"}).encode())
        .decode()
        .rstrip("=")
    )
    id_token = f"header.{payload}.sig"
    assert _google_email_from_id_token(id_token) == "me@gmail.com"
    assert _google_email_from_id_token("garbage") == ""
