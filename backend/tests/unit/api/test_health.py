"""GET /api/v1/health."""

from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import AppConfig
from app.main import create_app


async def test_health_returns_ok(app_config: AppConfig) -> None:
    application = create_app(app_config)
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as c:
        response = await c.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


async def test_openapi_is_versioned(app_config: AppConfig) -> None:
    application = create_app(app_config)
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as c:
        response = await c.get("/api/v1/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/health" in response.json()["paths"]


async def _get(application: object, path: str) -> tuple[int, dict[str, object]]:
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as c:  # type: ignore[arg-type]
        response = await c.get(path)
    return response.status_code, response.json()


async def test_ready_returns_200_with_working_database(
    app_config: AppConfig, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    application = create_app(app_config)
    application.state.session_factory = session_factory
    status, body = await _get(application, "/api/v1/health/ready")
    assert status == 200
    assert body == {"status": "ready", "checks": {"database": "ok"}}


async def test_ready_returns_503_when_database_breaks(
    app_config: AppConfig,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def broken(*_a: object, **_k: object) -> None:
        raise ConnectionError("db down")

    monkeypatch.setattr(AsyncSession, "execute", broken)
    application = create_app(app_config)
    application.state.session_factory = session_factory
    status, body = await _get(application, "/api/v1/health/ready")
    assert status == 503
    assert body == {"status": "unavailable", "checks": {"database": "fail"}}


async def test_ready_returns_503_without_database_configured(app_config: AppConfig) -> None:
    status, body = await _get(create_app(app_config), "/api/v1/health/ready")
    assert status == 503
    assert body["status"] == "unavailable"


async def test_liveness_does_not_depend_on_database(app_config: AppConfig) -> None:
    status, _ = await _get(create_app(app_config), "/api/v1/health")
    assert status == 200


async def test_lifespan_creates_and_disposes_engine(
    app_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_env = SimpleNamespace(database_url=SecretStr("sqlite+aiosqlite:///:memory:"))
    monkeypatch.setattr("app.main.get_env_settings", lambda: fake_env)
    application = create_app(app_config)
    async with application.router.lifespan_context(application):
        engine = application.state.engine
        assert engine is not None
        status, body = await _get(application, "/api/v1/health/ready")
        assert (status, body["status"]) == (200, "ready")
    assert application.state.engine is None
    assert application.state.session_factory is None


async def test_lifespan_without_database_url_still_starts(
    app_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.main.get_env_settings", lambda: SimpleNamespace(database_url=None))
    application = create_app(app_config)
    async with application.router.lifespan_context(application):
        status, _ = await _get(application, "/api/v1/health/ready")
        assert status == 503
