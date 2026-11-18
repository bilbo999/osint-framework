"""FastAPI application factory. Run with: uvicorn app.main:app --reload"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.core.config import AppConfig, get_config
from app.core.settings import get_env_settings
from app.db.session import create_engine, create_session_factory

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Create the DB engine on startup and dispose it on shutdown.

    Without DATABASE_URL the app still starts (liveness works) but readiness reports 503.
    """
    secret = get_env_settings().database_url
    application.state.engine = None
    application.state.session_factory = None
    if secret is None:
        log.warning("database_url_not_set", detail="/health/ready will return 503")
    else:
        engine = create_engine(secret.get_secret_value())
        application.state.engine = engine
        application.state.session_factory = create_session_factory(engine)
    try:
        yield
    finally:
        engine = application.state.engine
        if engine is not None:
            await engine.dispose()
        application.state.engine = None
        application.state.session_factory = None


def create_app(config: AppConfig | None = None) -> FastAPI:
    cfg = config or get_config()
    application = FastAPI(
        title=cfg.settings.app.name,
        version=__version__,
        openapi_url=f"{cfg.settings.app.api_prefix}/openapi.json",
        docs_url=f"{cfg.settings.app.api_prefix}/docs",
        redoc_url=f"{cfg.settings.app.api_prefix}/redoc",
        lifespan=lifespan,
    )
    if cfg.settings.app.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=cfg.settings.app.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Content-Type", cfg.settings.security.csrf_header_name, "Authorization"],
        )
    application.include_router(api_router, prefix=cfg.settings.app.api_prefix)
    return application


app = create_app()
