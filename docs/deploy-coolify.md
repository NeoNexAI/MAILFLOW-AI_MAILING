# Deploy en Coolify (VPS Hostinger) — guía paso a paso

> Despliegue de MailFlow en un VPS propio con [Coolify](https://coolify.io)
> ya instalado. Cubre tanto **self-host single-tenant** (tu instancia personal)
> como **SaaS multi-tenant** (la diferencia es un puñado de variables).
>
> Requisitos: VPS con Coolify funcionando, un dominio con DNS bajo tu control,
> y este repositorio accesible desde Coolify (GitHub App o deploy key).

## 0. Decide los dominios

Crea 2 registros DNS tipo A (o CNAME) apuntando a la IP del VPS:

| Subdominio | Servicio | Ejemplo |
|---|---|---|
| `app.` | web (Next.js) | `app.tudominio.com` |
| `api.` | api (FastAPI) | `api.tudominio.com` |

Coolify emite TLS automáticamente (Let's Encrypt) al asignar el dominio a cada app.

## 1. Crea el proyecto y las bases de datos

1. Coolify → **Projects → + New** → `mailflow` (elige el *environment* `production`).
2. **+ New Resource → Database → PostgreSQL** (la imagen por defecto vale; si
   quieres pgvector para features futuras usa la imagen `pgvector/pgvector:pg17`).
   - Apunta usuario/contraseña/DB generados. La URL interna tendrá la forma
     `postgresql://USER:PASS@HOST:5432/DB` (host interno del contenedor).
3. **+ New Resource → Database → Redis** (Redis 7). Apunta su URL interna.

> Usa siempre las **URLs internas** de Coolify para que api/worker hablen con
> las DBs por la red interna de Docker, sin exponer puertos al exterior.

## 2. Crea las 3 aplicaciones desde el repo

Para cada una: **+ New Resource → Application → (tu fuente Git) → este repo**,
build pack **Dockerfile**, rama `main`.

| App | Dockerfile (`Build → Dockerfile Location`) | Puerto | Dominio |
|---|---|---|---|
| `mailflow-api` | `infrastructure/docker/Dockerfile.api` | 8000 | `api.tudominio.com` |
| `mailflow-worker` | `infrastructure/docker/Dockerfile.worker` | — (sin dominio) | — |
| `mailflow-web` | `infrastructure/docker/Dockerfile.web` | 3000 | `app.tudominio.com` |

Notas:
- **Build context = raíz del repo** (los Dockerfiles copian `apps/` y `packages/`).
- `mailflow-web`: añade el **build arg** `NEXT_PUBLIC_API_URL=https://api.tudominio.com`
  (las variables `NEXT_PUBLIC_*` se hornean en build, no en runtime).
- `mailflow-worker` no expone puerto ni dominio.

## 3. Variables de entorno

En `mailflow-api` y `mailflow-worker` (los dos necesitan DB/Redis/SECRET_KEY):

```bash
DATABASE_URL=postgresql+asyncpg://USER:PASS@HOST-INTERNO:5432/DB   # ¡con +asyncpg!
REDIS_URL=redis://HOST-INTERNO-REDIS:6379/0
SECRET_KEY=<genera una NUEVA, nunca la de ejemplo>
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Solo en `mailflow-api`:

```bash
# Self-host personal (recomendado para empezar):
AUTH_MODE=single
SINGLE_TENANT_API_KEY=<token aleatorio largo>   # OBLIGATORIO al exponer a internet
CORS_ORIGINS=https://app.tudominio.com

# OAuth de buzones (cuando tengas las apps de Google/Azure):
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
OAUTH_REDIRECT_BASE=https://api.tudominio.com
OAUTH_SUCCESS_REDIRECT=https://app.tudominio.com/app/dashboard

# SaaS multi-tenant (solo si vas a operar para terceros):
# AUTH_MODE=multi
# STRIPE_SECRET_KEY=... STRIPE_WEBHOOK_SECRET=...
# STRIPE_PRICE_PRO=price_... STRIPE_PRICE_TEAM=price_...
# BILLING_SUCCESS_URL=https://app.tudominio.com/app/billing?status=success
# BILLING_CANCEL_URL=https://app.tudominio.com/app/billing?status=cancel
```

En `mailflow-web` (runtime; el API URL ya va horneado por build arg):

```bash
NODE_ENV=production
```

> ⚠️ La clave `SECRET_KEY` cifra las credenciales IMAP/LLM en la DB. Genera una
> nueva y **no uses jamás** la del `.env` de desarrollo (está quemada en el
> historial git — ver `SECURITY.md`).

## 4. Orden de arranque y healthchecks

1. **Deploy de Postgres y Redis** primero (estado *running*).
2. **Deploy `mailflow-api`**: su entrypoint ejecuta `alembic upgrade head`
   automáticamente (crea/actualiza el esquema) y arranca uvicorn.
   - Healthcheck en Coolify: path `/health`, puerto 8000 (devuelve 200 si la DB responde).
3. **Deploy `mailflow-worker`** (depende de que la DB ya esté migrada por el api).
4. **Deploy `mailflow-web`**.

Verifica:

```bash
curl https://api.tudominio.com/health   # {"status":"ok","db":"up",...}
# y abre https://app.tudominio.com → onboarding
```

## 5. Despliegue continuo

En cada app: **Settings → Webhooks** → activa el webhook de GitHub para que
cada push a `main` redepliegue. (Recomendado: solo después de que el CI esté
verde — Coolify también permite *manual deploy* si prefieres controlar cuándo.)

## 6. Backups

- **Postgres**: Coolify → tu base de datos → **Backups** → programa un backup
  diario (local y/o a S3-compatible). Es un `pg_dump` gestionado.
- Antes de cualquier actualización con migración, ten un backup reciente
  (las migraciones corren solas al desplegar el api).

## 7. Operación

| Tarea | Dónde |
|---|---|
| Logs api/worker/web | Coolify → app → **Logs** |
| Reiniciar un servicio | Coolify → app → **Restart** |
| Forzar un ciclo de una cuenta | botón "Run cycle now" en el dashboard, o `POST /accounts/{id}/cycles/run` |
| Ver historial de procesamiento | dashboard → cuenta → *Cycle history* (tabla `audit_log`) |
| Rotar `SECRET_KEY` | genera nueva → actualiza env en api+worker → redeploy. ⚠️ invalida credenciales cifradas: habrá que reconectar buzones/LLM |
| Actualizar | push a `main` (webhook) o **Deploy** manual; migraciones automáticas |

## 8. Checklist final

- [ ] DNS `app.` y `api.` → VPS, TLS emitido por Coolify
- [ ] `SECRET_KEY` nueva (no la de dev) en api y worker
- [ ] `SINGLE_TENANT_API_KEY` definida (la API nunca abierta a internet)
- [ ] `CORS_ORIGINS` = dominio real de la web
- [ ] `NEXT_PUBLIC_API_URL` (build arg de la web) = dominio real del api
- [ ] `/health` devuelve 200; onboarding carga
- [ ] Backup diario de Postgres programado
- [ ] (OAuth) redirect URIs registrados: `https://api.tudominio.com/oauth/{gmail|microsoft}/callback`
