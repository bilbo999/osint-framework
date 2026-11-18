"""Liveness (`/health`) and readiness (`/health/ready`). Neo4j/Redis checks arrive in Phase 6."""

from typing import Literal

import sqlalchemy as sa
import structlog
from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import __version__

router = APIRouter(tags=["health"])
log = structlog.get_logger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "unavailable"]
    checks: dict[str, Literal["ok", "fail"]]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@router.get("/health/ready", response_model=ReadinessResponse)
async def ready(request: Request, response: Response) -> ReadinessResponse:
    """200 when PostgreSQL answers `SELECT 1`; 503 otherwise (no details leaked)."""
    database_ok = False
    factory: async_sessionmaker[AsyncSession] | None = getattr(
        request.app.state, "session_factory", None
    )
    if factory is not None:
        try:
            async with factory() as session:
                await session.execute(sa.text("SELECT 1"))
            database_ok = True
        except Exception as exc:
            log.warning("readiness_database_check_failed", error=type(exc).__name__)
    if not database_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if database_ok else "unavailable",
        checks={"database": "ok" if database_ok else "fail"},
    )
