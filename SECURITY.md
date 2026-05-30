# Security

## Reporting

Found a vulnerability? Please open a private security advisory on GitHub rather
than a public issue.

## Secrets handling

- **Never commit `.env` files.** Per-app env files (`apps/*/.env`) and any
  `*.env` are gitignored. The application reads configuration from environment
  variables (see `.env.example`).
- `SECRET_KEY` is a Fernet key that encrypts stored credentials (IMAP passwords,
  LLM API keys). Generate one with:
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- In production, inject secrets via your platform's secret manager (Fly/Railway/
  AWS/Hetzner) or Docker/Kubernetes secrets — not via committed files.

## Known exposure — rotate before any real deployment

An early commit tracked `apps/api/.env` containing a development `SECRET_KEY`
(`qdCa5nGhLjd8qY0CCaQP2dE000lbSYDmtPnhzAVeVgs=`). The file has been removed from
version control and is now gitignored.

This key was only ever used for local development and tests, but because it
exists in git history it **must be treated as compromised**:

- **Do not** reuse it for any real deployment. Generate a fresh `SECRET_KEY`.
- Any data encrypted with the old key (none in production yet) should be
  re-encrypted under the new key.
- The same value still appears intentionally in tests as a fixed test key; that
  is fine because it never protects real data.

> Optional hardening: purge the key from git history with `git filter-repo`
> followed by a force-push. Deferred here because it rewrites shared history;
> rotating the key achieves the security goal without that disruption.
