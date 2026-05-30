"""Alembic env.py — configurado para SQLAlchemy async + autodescubrimiento de modelos."""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Importar todos los modelos para registrarlos en Base.metadata
from app.models import Base  # noqa: F401 — side-effect: registra todos los modelos

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DATABASE_URL del entorno tiene prioridad sobre el valor de alembic.ini, de modo
# que las migraciones funcionan en cualquier despliegue (Docker, CI, self-host)
# sin editar el .ini. Si no está, se usa el de alembic.ini.
_env_url = os.getenv("DATABASE_URL")
if _env_url:
    config.set_main_option("sqlalchemy.url", _env_url)

target_metadata = Base.metadata


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    url = config.get_main_option("sqlalchemy.url")
    connectable = create_async_engine(url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


run_migrations_online()
