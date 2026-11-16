"""Shared fixtures. Tests never hit real external services."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.collectors.base import CollectorDependencies
from app.core.config import AppConfig, CollectorConfig, load_config
from app.core.settings import REPO_ROOT
from app.domain import Target, TargetType

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
