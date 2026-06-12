# M1.1 — Diseño: Identidad SaaS con Better Auth (BFF)

**Estado:** diseño aprobado-pendiente-de-implementación · **Esfuerzo:** XL (3 PRs)
**Resuelve:** SEC-2 (API key del tenant expuesta en el bundle del navegador) y
ARCH-3 (sin signup/login: las orgs solo se crean tocando la DB).

## 1. Objetivos / No-objetivos

**Objetivos**
1. Un usuario puede **registrarse, iniciar sesión y obtener su organización**
   sin que nadie toque la base de datos.
2. La **API key de la org nunca llega al navegador** — desaparece
   `NEXT_PUBLIC_API_KEY`.
3. El **self-host single-tenant no cambia**: sigue funcionando sin Better Auth
   (AUTH_MODE=single), con su flujo actual.
4. Base para Team: organizaciones con **miembros e invitaciones** (lo usa M1.5
   para asientos).

**No-objetivos (ahora)**
- SSO/SAML empresarial (post-launch, plan Team v2).
- Migrar el API key auth del FastAPI: **se mantiene** como mecanismo
  server-to-server (y para usuarios API/power users).
- Roles finos por miembro (solo `owner`/`member` de Better Auth).

## 2. Decisión de arquitectura: patrón BFF

De las tres opciones evaluadas (A: FastAPI verifica JWT de Better Auth;
B: sesión compartida por cookie + introspección; **C: BFF**), se elige **C**:

> **El navegador solo habla con Next.js.** Better Auth vive en el servidor
> Next (route handler `/api/auth/[...all]`) con cookies httpOnly. Para los
> datos de MailFlow, el navegador llama a **route handlers proxy** de Next
> (`/api/mf/*`), que validan la sesión, recuperan la API key de la org
> **en el servidor** y reenvían la petición al FastAPI con `X-API-Key`.

**Por qué C:** cero cambios en el modelo de auth del FastAPI (ya probado, con
aislamiento por org testeado); la API key queda confinada al servidor web; el
API sigue siendo utilizable directamente por curl/scripts con la misma key; y
es el patrón con menor superficie nueva de seguridad. El coste es un hop extra
(web→api), irrelevante a esta escala y dentro de la misma red Docker.

## 3. Componentes y flujos

```
Navegador ──(cookies httpOnly)──► Next.js (apps/web)
                                   ├─ /api/auth/[...all]  ← Better Auth (signup/login/orgs)
                                   └─ /api/mf/[...path]   ← proxy: sesión → org → X-API-Key → FastAPI
                                                │
                                       (red interna, server-to-server)
                                                ▼
                                          FastAPI (apps/api)  ← sin cambios de auth
                                                ▼
                                            PostgreSQL (compartido)
```

### 3.1 Better Auth en `apps/web`
- Deps: `better-auth` + adaptador Postgres (`pg`/kysely). **Mismo Postgres** que
  el API, tablas propias de Better Auth (`user`, `session`, `account`,
  `organization`, `member`, `invitation` — las crea su CLI de migración).
  Nota: su tabla `organization` es distinta de la `organizations` del API; el
  vínculo es la columna `metadata` (ver 3.2).
- Plugins: `organization()` (orgs + members + invitaciones por email) y
  email+password (mínimo viable; social login del *usuario* es opcional post-MVP).
- Config server: `lib/auth.ts` (instancia), handler `app/api/auth/[...all]/route.ts`,
  cliente `lib/auth-client.ts` para las páginas de login/signup.

### 3.2 Aprovisionamiento de la org (hook de creación)
Al crear una organización en Better Auth (hook `organization.creation.afterCreate`):
1. El servidor web llama a un endpoint **interno** nuevo del FastAPI:
   `POST /internal/orgs {name, slug}` autenticado con el header
   `X-Internal-Secret: $INTERNAL_API_SECRET` (secreto compartido web↔api,
   solo red interna; 403 si no coincide y 501 si no está configurado).
2. El FastAPI crea la fila en SU tabla `organizations`, genera la API key
   (`generate_api_key()` ya existente, hash en DB) y devuelve
   `{org_id, api_key}` — única vez que la key viaja (server-to-server).
3. El hook guarda `{mf_org_id, mf_api_key}` **cifrados** en el campo `metadata`
   de la organización de Better Auth (cifrado con `WEB_SECRET_KEY`, Fernet-like
   en TS o AES-GCM de WebCrypto).

### 3.3 El proxy `/api/mf/[...path]`
Route handler catch-all en Next:
1. `auth.api.getSession()` → 401 si no hay sesión.
2. Org activa de la sesión → lee `mf_api_key` del metadata (descifra).
3. `fetch(`${API_INTERNAL_URL}${path}`)` reenviando método/cuerpo/query +
   `X-API-Key`. Allowlist de paths (`/accounts`, `/llm-providers`, `/oauth`,
   `/billing`, `/health`) — nunca `/internal/*`.
4. El cliente actual (`src/lib/api.ts`) solo cambia su base: de
   `NEXT_PUBLIC_API_URL` directa a `/api/mf` (mismo contrato de tipos).

### 3.4 OAuth de buzones a través del BFF
`/oauth/{provider}/authorize` ya devuelve la URL de consentimiento vía API
key (el proxy la cubre). El **callback** sigue llegando directo al FastAPI
(redirect del proveedor) — sin cambios: el `state` firmado ya lleva el org_id.

### 3.5 Modos de despliegue
| | single (self-host) | multi (SaaS) |
|---|---|---|
| Better Auth | desactivado (`WEB_AUTH=off`): la web usa el flujo actual | activo: login obligatorio para `/app/*` y `/onboarding` |
| API key en web | `SINGLE_TENANT_API_KEY` opcional server-side | del metadata de la org, server-side |
| FastAPI | sin cambios | sin cambios (+ `/internal/orgs`) |

## 4. Cambios por componente

| Componente | Cambio | Tamaño |
|---|---|---|
| `apps/web` | better-auth + adaptador pg, `lib/auth.ts`, handler, páginas `/login` `/signup` `/app/settings/members`, middleware de protección de `/app/*`, proxy `/api/mf/*`, migrar `lib/api.ts` a base `/api/mf` | L |
| `apps/api` | `POST /internal/orgs` (router nuevo `internal.py`, guard por `INTERNAL_API_SECRET`), tests | S |
| DB | tablas de Better Auth (su CLI), sin tocar las del API | S |
| Infra | env nuevos: `INTERNAL_API_SECRET` (api+web), `WEB_SECRET_KEY`, `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, `DATABASE_URL` (web), `API_INTERNAL_URL` (web→api interno); compose + guía Coolify | S |

## 5. Seguridad
- Cookies de sesión httpOnly+Secure+SameSite=Lax (Better Auth por defecto).
- La API key nunca en cliente: verificable con `grep NEXT_PUBLIC_API_KEY` = 0.
- `/internal/*` jamás expuesto por el proxy ni por dominio público (regla en
  el reverse proxy de Coolify o allowlist del handler).
- Rate limiting de login/signup: Better Auth trae rate limit integrado;
  habilitarlo (cubre parte de SEC-5).
- Invitaciones por email requieren proveedor SMTP/Resend (env opcional;
  sin él, invitación por enlace copiable).

## 6. Plan de implementación (3 PRs)
1. **PR A — API**: `POST /internal/orgs` + `INTERNAL_API_SECRET` + tests
   (S; sin riesgo, desplegable solo).
2. **PR B — Web auth**: Better Auth (tablas, login/signup, protección de
   rutas, org por defecto al registrarse vía hook→PR A), modo `WEB_AUTH=off`
   para self-host (M/L).
3. **PR C — Proxy BFF**: `/api/mf/*` + migrar `lib/api.ts` + eliminar
   `NEXT_PUBLIC_API_KEY` + página de members/invitaciones (M).

**Definition of done:** registro→onboarding→buzón conectado sin tocar la DB;
`NEXT_PUBLIC_API_KEY` eliminado del código; self-host single sin regresión
(e2e compose); tests de `/internal/orgs` (403 sin secreto, 501 sin config).

## 7. Riesgos
| Riesgo | Mitigación |
|---|---|
| Better Auth (lib joven) cambia APIs | fijar versión exacta; su core (sesiones/orgs) es estable desde 1.x |
| Doble tabla de organizaciones (BA + API) desincronizada | la fuente de verdad de *billing/cuotas* sigue siendo la del API; la de BA solo agrupa usuarios; vínculo unidireccional por metadata; job de reconciliación si hiciera falta |
| Self-host roto por auth | flag `WEB_AUTH=off` por defecto en single + test e2e del compose |
