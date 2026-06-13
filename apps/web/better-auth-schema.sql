-- Better Auth schema (SaaS / WEB_AUTH=on) for MailFlow.
--
-- GENERATED from apps/web/src/lib/auth.ts — regenerate with:
--   pnpm --filter @mailflow/web auth:generate
-- and re-apply the `if not exists` guards below (kept idempotent so it is safe
-- to run more than once and on a partially-migrated database).
--
-- Preferred path is the config-driven, diff-aware migrator:
--   pnpm --filter @mailflow/web auth:migrate
-- This raw SQL is provided to bootstrap a fresh database with only psql access
-- (e.g. a managed Postgres in Coolify) without a Node toolchain.
--
-- These tables live in the SAME Postgres as the API. They do NOT collide with
-- the API's Alembic tables: Better Auth uses singular `organization`/`user`/…,
-- the API uses `organizations` (plural), `email_accounts`, etc. The link
-- between them is `organization.metadata` (mf_org_id + encrypted mf_api_key).

create table if not exists "user" ("id" text not null primary key, "name" text not null, "email" text not null unique, "emailVerified" boolean not null, "image" text, "createdAt" timestamptz default CURRENT_TIMESTAMP not null, "updatedAt" timestamptz default CURRENT_TIMESTAMP not null);

create table if not exists "session" ("id" text not null primary key, "expiresAt" timestamptz not null, "token" text not null unique, "createdAt" timestamptz default CURRENT_TIMESTAMP not null, "updatedAt" timestamptz not null, "ipAddress" text, "userAgent" text, "userId" text not null references "user" ("id") on delete cascade, "activeOrganizationId" text);

create table if not exists "account" ("id" text not null primary key, "accountId" text not null, "providerId" text not null, "userId" text not null references "user" ("id") on delete cascade, "accessToken" text, "refreshToken" text, "idToken" text, "accessTokenExpiresAt" timestamptz, "refreshTokenExpiresAt" timestamptz, "scope" text, "password" text, "createdAt" timestamptz default CURRENT_TIMESTAMP not null, "updatedAt" timestamptz not null);

create table if not exists "verification" ("id" text not null primary key, "identifier" text not null, "value" text not null, "expiresAt" timestamptz not null, "createdAt" timestamptz default CURRENT_TIMESTAMP not null, "updatedAt" timestamptz default CURRENT_TIMESTAMP not null);

create table if not exists "organization" ("id" text not null primary key, "name" text not null, "slug" text not null unique, "logo" text, "createdAt" timestamptz not null, "metadata" text);

create table if not exists "member" ("id" text not null primary key, "organizationId" text not null references "organization" ("id") on delete cascade, "userId" text not null references "user" ("id") on delete cascade, "role" text not null, "createdAt" timestamptz not null);

create table if not exists "invitation" ("id" text not null primary key, "organizationId" text not null references "organization" ("id") on delete cascade, "email" text not null, "role" text, "status" text not null, "expiresAt" timestamptz not null, "createdAt" timestamptz default CURRENT_TIMESTAMP not null, "inviterId" text not null references "user" ("id") on delete cascade);

create index if not exists "session_userId_idx" on "session" ("userId");

create index if not exists "account_userId_idx" on "account" ("userId");

create index if not exists "verification_identifier_idx" on "verification" ("identifier");

create unique index if not exists "organization_slug_uidx" on "organization" ("slug");

create index if not exists "member_organizationId_idx" on "member" ("organizationId");

create index if not exists "member_userId_idx" on "member" ("userId");

create index if not exists "invitation_organizationId_idx" on "invitation" ("organizationId");

create index if not exists "invitation_email_idx" on "invitation" ("email");
