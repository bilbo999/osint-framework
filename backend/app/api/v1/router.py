"""Aggregates every v1 router. New resources are included here (Phase 8)."""

from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router)
