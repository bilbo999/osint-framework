"""Shared fixtures. Tests never hit real external services."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.collectors.base import CollectorDependencies
from app.core.config import AppConfig, CollectorConfig, load_config
from app.core.settings import REPO_ROOT
from app.db.base import Base
from app.db.session import create_engine, create_session_factory
from app.db.uow import UnitOfWork
from app.domain import Target, TargetType
from app.services.investigations import InvestigationService
from app.services.persistence import FindingPersister

FIXED_NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def app_config() -> AppConfig:
    return load_config(REPO_ROOT / "config")


@pytest.fixture
def collector_config(app_config: AppConfig) -> CollectorConfig:
    return app_config.collectors.defaults


@pytest.fixture
def investigation_id() -> UUID:
    return uuid4()


@pytest.fixture
def domain_target(investigation_id: UUID) -> Target:
    return Target(investigation_id=investigation_id, type=TargetType.DOMAIN, value="example.com")


@pytest.fixture
def fixed_deps() -> CollectorDependencies:
    return CollectorDependencies(clock=lambda: FIXED_NOW)


# --------------------------------------------------------------------------- database
@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """In-memory SQLite with the full schema (ADR-014); foreign keys enforced."""
    eng = create_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest.fixture
def uow_factory(session_factory: async_sessionmaker[AsyncSession]) -> Callable[[], UnitOfWork]:
    return lambda: UnitOfWork(session_factory)


@pytest.fixture
def investigation_service(uow_factory: Callable[[], UnitOfWork]) -> InvestigationService:
    return InvestigationService(uow_factory, clock=lambda: FIXED_NOW)


@pytest.fixture
def persister(uow_factory: Callable[[], UnitOfWork], app_config: AppConfig) -> FindingPersister:
    return FindingPersister(uow_factory, app_config.settings.evidence, clock=lambda: FIXED_NOW)
