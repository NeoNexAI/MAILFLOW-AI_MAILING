# MailFlow — Plan de ejecución hacia producción

## Context

Segundo producto del encargo `/ultracode`. Padel ya está cerrado y fusionado
(PR #59). Decisión del usuario: avanzar MailFlow con **OSS self-host + SaaS en
paralelo**. Sin deadline duro.

MailFlow es un SaaS open-source y self-hostable de clasificación y redacción de
emails con IA (LiteLLM/BYOK). Monorepo pnpm+turbo (TS) / uv (Python).

## Estado real verificado (vía git + ejecución local)

- Rama `claude/ultracode-prod-readiness-0DwLU` == `origin/main` (limpio). El
  remoto de esta rama se borró tras el merge de Padel (otra repo); push fresco.
- **Fase 1 (core) + Fase 2a (DB+worker) COMPLETAS.** `packages/core` (parser,
  cascada de clasificación, IMAP), `apps/api/app/{models,repositories,services}`,
  worker ARQ, migración Alembic `001_initial_schema` (8 tablas).
- **Toolchain OK aquí:** `uv sync --all-extras` funciona (baja Python 3.13).
  Baseline: ruff ✅, core 89 tests ✅, api unit no-DB 23 ✅. Las 12 pruebas de
  repositorio necesitan Postgres (no disponible en este entorno).

### Gaps reales encontrados (ground truth)
1. **`apps/api/.env` con `SECRET_KEY` (clave Fernet) COMMITEADO** pese a estar en
   `.gitignore` (force-add). Fuga de secreto → hay que `git rm --cached` + rotar nota.
2. **API = solo `/health` + `/`.** Sin rutas REST de dominio. Sin auth. Sin RLS.
3. **CI no corre `apps/api/tests/`** (solo `packages/core/tests/`). Los tests del
   API (servicio, worker, repos) no protegen nada en CI.
4. **CORS hardcodeado** a `http://localhost:3000` (no configurable por entorno).
5. **`/health` no comprueba la DB** (siempre "ok"). Sin logs estructurados.
6. Frontend `apps/web` = placeholder.

## Estrategia de entrega (incrementos pequeños, cada uno verde y en su PR)

Priorizo lo que es **común a OSS y SaaS** y desbloquea todo lo demás, antes que
features de un solo modo.

### PR 1 — Seguridad + saneamiento de base (este primer entregable)
Objetivo: cerrar la fuga de secreto y endurecer la base sin cambiar comportamiento.
- `git rm --cached apps/api/.env`; añadir `apps/api/.env` explícito a `.gitignore`;
  documentar en `.env.example` que `SECRET_KEY` se genera con
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
  Nota de rotación (la clave filtrada debe considerarse comprometida).
- **CORS configurable** por env (`CORS_ORIGINS`, default localhost) en `config.py` + `main.py`.
- **`/health` con check de DB** (SELECT 1) → 200/503, igual patrón que Padel.
- **CI: correr también `apps/api/tests/`** (job que ejecuta desde `apps/api`,
  `-m "not integration"`), con servicio Postgres para las pruebas de repos.
- Verificar: ruff, core tests, api unit tests verdes.

### PR 2 — Capa HTTP de dominio + auth (Fase 2b, núcleo común OSS+SaaS)
- Esqueleto de routers FastAPI: `/accounts`, `/llm-providers`, `/rules`,
  `/cycles` (CRUD mínimo) sobre los repos existentes; dependencia `get_session`.
- **AuthN**: middleware de API key/JWT con resolución de `org_id`. En modo
  **single-tenant** (`MAILFLOW_AUTH_MODE=single`) usa una org por defecto; en
  **multi-tenant** valida token. Esto habilita los dos modos a la vez.
- **AuthZ/aislamiento**: filtrado por `org_id` en cada repo + (SaaS) RLS Postgres.
- Manejo de errores tipado + logs estructurados JSON.
- Tests de rutas con `httpx.AsyncClient`.

### PR 3 — Resiliencia del worker + observabilidad (Fase 2 pendiente)
- Backoff exponencial (IMAP) + circuit breaker (LLM) + dead-letter / rollback de ciclo.
- Logs estructurados + métricas básicas; Sentry opcional DSN-guarded.

### PR 4 — Self-host runnable (Fase 4, modo OSS)
- `infrastructure/docker-compose.yml` self-host (web+api+worker+postgres/sqlite+redis),
  verificado; `docs/self-hosting.md`; modo single-tenant.

> Fases 3 (frontend), 5 (billing Stripe) y 6 (launch) quedan después; se planifican
> cuando PR 1–4 estén dentro. Billing es SaaS-only y el más tardío.

## Verificación (cada PR)
- `uv run ruff check .` + `uv run ruff format --check .`
- `uv run pytest packages/core/tests -m "not integration"` (≥80% cov core)
- `cd apps/api && uv run pytest tests -m "not integration"` (con Postgres en CI)
- `pnpm biome check .` + `pnpm typecheck` (TS) cuando se toque web.
- Cada PR: draft, CI verde, sin secretos, sin romper baseline.

## Decisión abierta para el usuario
Confirmar el alcance del **primer PR** (seguridad + saneamiento) antes de seguir
con la capa HTTP/auth, que es más grande y conviene revisar el enfoque de
auth (single vs multi-tenant flag) antes de construirlo.
