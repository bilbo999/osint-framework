"""GET /api/v1/health."""

from httpx import ASGITransport, AsyncClient

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
