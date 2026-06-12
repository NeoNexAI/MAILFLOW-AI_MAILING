# MailFlow

**Open source AI email assistant. Use any LLM. Your inbox, your rules, your privacy.**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![CI](https://github.com/JonatanGhub/mailflow/actions/workflows/ci.yml/badge.svg)](https://github.com/JonatanGhub/mailflow/actions/workflows/ci.yml)

MailFlow automatically classifies incoming emails into your IMAP folders and generates draft replies in your writing style — powered by **any LLM you choose** (local Ollama, OpenAI, Anthropic, Gemini, vLLM, LM Studio, or any OpenAI-compatible endpoint).

## Why MailFlow?

| Feature | MailFlow | Superhuman | Shortwave | Spark |
|---|---|---|---|---|
| Open source | ✅ AGPL | ❌ | ❌ | ❌ |
| Self-hostable | ✅ Docker | ❌ | ❌ | ❌ |
| Multi-LLM support | ✅ 100+ | ❌ GPT-only | ❌ Claude-only | ❌ |
| Privacy (local AI) | ✅ Ollama | ❌ | ❌ | ❌ |
| Bilingual EN/ES | ✅ | ❌ | ❌ | ❌ |
| Price | Free / $12/mo | $30-40/mo | $24/mo | $10/mo |

## Quick Start (Self-hosted)

```bash
git clone https://github.com/JonatanGhub/mailflow.git
cd mailflow
cp .env.example .env
# Set SECRET_KEY in .env (a Fernet key):
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
docker compose -f infrastructure/docker-compose.yml up -d --build
```

This brings up the full stack (postgres + redis + API + worker + web); the API
migrates the database on startup. Then open:

- **Web app**: <http://localhost:3000> — onboarding wizard + dashboard
- API health: `curl http://localhost:8000/health`
- API docs: <http://localhost:8000/docs>

See **[docs/self-hosting.md](docs/self-hosting.md)** for full configuration and
operations.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 (App Router) |
| Backend API | Python 3.13 + FastAPI |
| Workers | ARQ (asyncio jobs) |
| Database | PostgreSQL |
| Auth | API-key per organization (multi-tenant); Better Auth integration planned |
| LLM Router | LiteLLM (100+ providers) |
| Email | IMAP + M365 OAuth2 + Gmail OAuth2 |

## Features

- **Auto-classification** — deterministic cascade (internal/client domain → thread → keyword) + LLM fallback
- **Draft generation** — replies saved as IMAP Drafts (never auto-sent)
- **Multi-LLM** — choose any engine per workspace: Ollama, OpenAI, Anthropic, Gemini, vLLM…
- **One-click mailbox connect** — Gmail / Microsoft 365 via OAuth2, or generic IMAP
- **Web dashboard** — onboarding wizard, mailboxes, cycle history & stats, billing
- **Multi-tenant SaaS or single-tenant self-host** — same codebase, one env var

### Roadmap (not yet implemented)

- Template library with keyword auto-detection
- Learning loop (corrections feed back into future drafts)
- Writing-style capture, semantic search

## Development

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for setup instructions.

```bash
# Backend
uv sync
uvicorn apps.api.app.main:app --reload

# Frontend
pnpm install
pnpm dev
```

## License

GNU Affero General Public License v3.0 — see [LICENSE](LICENSE).

Commercial SaaS use requires a commercial license. Contact tecnicosestudios@igex.es.
