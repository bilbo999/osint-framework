"""FastAPI application factory. Run with: uvicorn app.main:app --reload"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.core.config import AppConfig, get_config


def create_app(config: AppConfig | None = None) -> FastAPI:
    cfg = config or get_config()
    application = FastAPI(
        title=cfg.settings.app.name,
        version=__version__,
        openapi_url=f"{cfg.settings.app.api_prefix}/openapi.json",
        docs_url=f"{cfg.settings.app.api_prefix}/docs",
        redoc_url=f"{cfg.settings.app.api_prefix}/redoc",
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
