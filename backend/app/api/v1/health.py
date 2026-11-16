"""Liveness endpoint. Readiness checks for PostgreSQL/Neo4j/Redis are added in Phase 2/6."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)
