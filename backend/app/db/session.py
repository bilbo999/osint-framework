"""Async engine / session factory and the FastAPI session dependency."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.settings import get_env_settings


def database_url_from_env() -> str:
    secret = get_env_settings().database_url
    if secret is None:
        raise RuntimeError("DATABASE_URL is not set (see .env.example)")
    return secret.get_secret_value()


def create_engine(url: str | None = None, *, echo: bool = False) -> AsyncEngine:
    """Create the async engine. SQLite gets foreign keys enabled so cascades work in tests."""
    url = url or database_url_from_env()
    kwargs: dict[str, Any] = {"echo": echo}
    is_sqlite = url.startswith("sqlite")
    if is_sqlite and (":memory:" in url or url.endswith("///")):
        kwargs.update(poolclass=StaticPool, connect_args={"check_same_thread": False})
    elif not is_sqlite:
        kwargs["pool_pre_ping"] = True
    engine = create_async_engine(url, **kwargs)
    if is_sqlite:

        @event.listens_for(engine.sync_engine, "connect")
        def _enable_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: attributes stay readable after commit (no lazy IO in async).
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, closed (rolled back) on exit."""
    factory: async_sessionmaker[AsyncSession] | None = getattr(
        request.app.state, "session_factory", None
    )
    if factory is None:
        raise RuntimeError("database is not configured")
    async with factory() as session:
        yield session
