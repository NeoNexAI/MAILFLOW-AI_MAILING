"""Tests para app.auth — hashing y generación de API keys."""

from __future__ import annotations

from app.auth import generate_api_key, hash_api_key


def test_hash_is_deterministic_and_hex64():
    h1 = hash_api_key("mf_abc")
    h2 = hash_api_key("mf_abc")
    assert h1 == h2
    assert len(h1) == 64
    assert all(c in "0123456789abcdef" for c in h1)


def test_different_keys_hash_differently():
    assert hash_api_key("mf_a") != hash_api_key("mf_b")


def test_generate_api_key_returns_prefixed_key_and_matching_hash():
    raw, h = generate_api_key()
    assert raw.startswith("mf_")
    assert h == hash_api_key(raw)
    # La clave en claro debe ser razonablemente larga (entropía).
    assert len(raw) > 20
