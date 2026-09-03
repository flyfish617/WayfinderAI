from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.v1 import auth as auth_v1
from .api.v1 import trip as trip_v1
from .api.dependencies import get_trip_service
from .config import settings
from .exceptions.exception_handler import global_exception_handler
from .middleware.auth import AuthMiddleware
from .middleware.rate_limit import RateLimitMiddleware, RateLimiter
from .middleware.request_id import RequestIDMiddleware
from .observability.logger import setup_logger
from .services.vector_memory_service import vector_memory_service

logger = setup_logger(
    name="trip_planner",
    log_level=settings.LOG_LEVEL,
    enable_file_logging=True,
    enable_console_logging=True,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trip Planner API",
        description="Trip planning service powered by LLM agents.",
        version="1.0.0",
    )
    app.add_exception_handler(Exception, global_exception_handler)
    _configure_middleware(app)
    _configure_static_files(app)
    _configure_routes(app)
    _register_events(app)
    return app


def _configure_middleware(app: FastAPI) -> None:
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        AuthMiddleware,
        jwt_secret=settings.JWT_SECRET,
        jwt_expiry_hours=settings.JWT_EXPIRY_HOURS,
    )
    app.add_middleware(
        RateLimitMiddleware,
        rate_limiter=RateLimiter(global_rate=100, per_ip_rate=20, enabled=True),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_origins_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _configure_static_files(app: FastAPI) -> None:
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


def _configure_routes(app: FastAPI) -> None:
    app.include_router(trip_v1.router, prefix="/api/v1/trips", tags=["Trip Planning"])
    app.include_router(auth_v1.router, prefix="/api/v1/auth", tags=["Authentication"])

    @app.get("/health", tags=["Health Check"])
    def health_check():
        return {"status": "ok"}


def _register_events(app: FastAPI) -> None:
    @app.on_event("startup")
    def on_startup():
        logger.info("Trip Planner API started")
        logger.info("Vector memory stats", extra={"stats": vector_memory_service.get_stats()})
        get_trip_service().start_async_workers()


app = create_app()
