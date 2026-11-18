"""Async Alembic environment. The URL comes from DATABASE_URL (never from alembic.ini).

Tests may inject a URL with ``config.attributes["database_url"] = "..."``.
"""

from __future__ import annotations

import asyncio

from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import context
from app.db.base import Base
from app.db.session import create_engine, database_url_from_env
from app.models import *  # noqa: F403  (registers every table on Base.metadata)

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    injected = config.attributes.get("database_url")
    return str(injected) if injected else database_url_from_env()


def _configure(**kwargs: object) -> None:
    context.configure(
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=False,
        **kwargs,  # type: ignore[arg-type]
    )


def run_migrations_offline() -> None:
    _configure(url=_database_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def _run_sync(connection: Connection) -> None:
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine: AsyncEngine = create_engine(_database_url())
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run_sync)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
