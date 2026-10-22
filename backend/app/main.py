from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from app.api.v1.endpoints.health import router as health_probe_router
from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import logger
from app.db.session import close_db, get_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application lifecycle events (startup and graceful shutdown)."""
    settings = get_settings()
    logger.info(
        f"Starting {settings.app_name} v{settings.app_version} [{settings.environment}]"
    )

    # Initialize database connection pool
    try:
        get_engine()
        logger.info("Database engine connectivity verified.")
        from app.db.seed import seed_demo_accounts
        await seed_demo_accounts()
    except Exception as exc:
        logger.error(f"Error during database startup initialization: {exc}")

    yield

    # Clean up resources on shutdown
    logger.info("Initiating graceful shutdown...")
    await close_db()
    logger.info("Application shutdown complete.")


def create_application() -> FastAPI:
    """FastAPI application factory function."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Enterprise Financial Document Intelligence Platform API",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # Centralized exception handlers
    register_exception_handlers(app)

    # Middleware configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Direct top-level health probe routes (e.g. /health/live, /health/ready for K8s/Docker)
    app.include_router(health_probe_router, prefix="/health", tags=["Root Health"])

    # Versioned API routes (e.g. /api/v1/health/live, /api/v1/documents)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["Root"])
    async def root_info():
        """Root API metadata and documentation link."""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "status": "operational",
            "docs": "/docs" if settings.debug else "disabled",
            "api_v1": settings.api_v1_prefix,
            "health": {
                "live": "/health/live",
                "ready": "/health/ready",
            },
        }

    return app


app = create_application()
