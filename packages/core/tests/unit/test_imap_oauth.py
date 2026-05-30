"""Tests del modo OAuth (XOAUTH2) de ImapGenericProvider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mailflow_core.providers.imap_generic import ImapGenericProvider


@pytest.fixture()
def mock_imap():
    with patch("mailflow_core.providers.imap_generic.imapclient.IMAPClient") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        instance.list_folders.return_value = [([], b"/", "INBOX")]
        yield instance


def test_requires_password_or_token():
    with pytest.raises(ValueError):
        ImapGenericProvider(host="imap.x.com", port=993, username="u")


def test_oauth_uses_xoauth2_login(mock_imap):
    provider = ImapGenericProvider(
        host="imap.gmail.com",
        port=993,
        username="user@gmail.com",
        access_token="ya29.token",
    )
    provider.connect()
    mock_imap.oauth2_login.assert_called_once_with("user@gmail.com", "ya29.token")
    mock_imap.login.assert_not_called()


def test_password_uses_plain_login(mock_imap):
    provider = ImapGenericProvider(host="imap.x.com", port=993, username="u", password="pw")
    provider.connect()
    mock_imap.login.assert_called_once_with("u", "pw")
    mock_imap.oauth2_login.assert_not_called()
