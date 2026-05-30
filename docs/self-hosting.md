# Self-hosting MailFlow

Run MailFlow on your own server with Docker. This sets up the full stack — the
web app, the API, and the worker that classifies your email and writes draft
replies.

## Requirements

- Docker + Docker Compose v2 (`docker compose`, not the old `docker-compose`).
- An IMAP mailbox (host, username, password). OAuth (Gmail/M365) comes later.
- An LLM endpoint: a local [Ollama](https://ollama.com) (recommended for
  privacy) or any OpenAI-compatible API.

## 1. Clone and configure

```bash
git clone https://github.com/JonatanGhub/mailflow.git
cd mailflow
cp .env.example .env
```

Edit `.env` and set **at least** `SECRET_KEY` (everything else has sane
defaults for a local single-tenant deployment):

```bash
# Generate a Fernet key for SECRET_KEY:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Key variables (see `.env.example` for the full list):

| Variable | Default | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | — (**required**) | Fernet key encrypting stored credentials |
| `AUTH_MODE` | `single` | `single` = one local org, no token needed |
| `SINGLE_TENANT_API_KEY` | empty | optional key to lock the local API |
| `POSTGRES_PASSWORD` | `mailflow` | change for anything internet-facing |
| `API_PORT` | `8000` | host port for the API |
| `WEB_PORT` | `3000` | host port for the web app |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | API URL baked into the web build |
| `CORS_ORIGINS` | `http://localhost:3000` | allowed browser origins |

## 2. Start

```bash
docker compose -f infrastructure/docker-compose.yml up -d --build
```

This starts **postgres**, **redis**, **api**, **worker**, and **web**. The API
container runs database migrations (`alembic upgrade head`) automatically before
serving.

Then open the web app at **<http://localhost:3000>** and follow the onboarding
wizard (connect an LLM provider, then a mailbox). Health and docs:

```bash
curl http://localhost:8000/health   # {"status":"ok","db":"up",...}
```

Interactive API docs: <http://localhost:8000/docs>.

## 3. Connect a mailbox (via API, optional)

The web onboarding does this for you. If you prefer the API directly:

In single-tenant mode no auth header is required (unless you set
`SINGLE_TENANT_API_KEY`, in which case add `-H "X-API-Key: <key>"`).

```bash
# Configure an LLM provider (example: local Ollama)
curl -X POST http://localhost:8000/llm-providers \
  -H 'Content-Type: application/json' \
  -d '{
    "label": "Local Ollama",
    "type": "ollama",
    "base_url": "http://host.docker.internal:11434",
    "default_classification_model": "ollama/llama3.1:8b",
    "default_generation_model": "ollama/llama3.1:8b"
  }'

# Connect an IMAP account
curl -X POST http://localhost:8000/accounts \
  -H 'Content-Type: application/json' \
  -d '{
    "imap_host": "imap.example.com",
    "username": "you@example.com",
    "password": "app-password",
    "interval_minutes": 5
  }'
```

The worker picks up due accounts on its 5-minute cron. To trigger a cycle
immediately:

```bash
curl -X POST http://localhost:8000/accounts/<ACCOUNT_ID>/cycles/run
```

Inspect processing history:

```bash
curl http://localhost:8000/accounts/<ACCOUNT_ID>/cycles
```

## 4. Operations

- **Logs**: `docker compose -f infrastructure/docker-compose.yml logs -f api worker`
- **Stop**: `docker compose -f infrastructure/docker-compose.yml down`
- **Reset everything** (deletes data): add `-v` to remove the volumes.
- **Upgrade**: `git pull` then re-run the `up -d --build` command; migrations
  apply automatically.
- **Backups**: the data lives in the `postgres_data` volume. Use `pg_dump`
  against the postgres container for logical backups.

## Notes

- MailFlow **never sends email** — drafts are saved to your IMAP Drafts folder.
- Multi-tenant (SaaS) mode (`AUTH_MODE=multi`) exists for hosted deployments;
  for self-host keep the default `single`.
- For internet-facing deployments, put the API behind a TLS-terminating reverse
  proxy (Caddy/Nginx/Traefik) and set strong `POSTGRES_PASSWORD` and
  `SINGLE_TENANT_API_KEY`.
