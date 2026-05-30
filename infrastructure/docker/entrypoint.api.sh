#!/usr/bin/env sh
# Entrypoint del contenedor API: aplica migraciones y arranca el servidor.
# alembic lee DATABASE_URL del entorno (ver apps/api/alembic/env.py).
set -e

echo "[entrypoint] Aplicando migraciones (alembic upgrade head)..."
cd /app/apps/api
uv run alembic upgrade head
cd /app

echo "[entrypoint] Arrancando API (uvicorn)..."
exec uv run uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8000
