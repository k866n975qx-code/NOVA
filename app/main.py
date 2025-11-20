from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.logging_config import configure_logging, get_logger

# Configure logging first so all later imports use it
configure_logging()
logger = get_logger("nova.api")

# Import settings AFTER logging is configured
from app.config.settings import settings  # noqa: E402
from app.models.base import BaseResponse, Meta, ErrorResponse, ErrorInfo  # noqa: E402

from app.routers.core import router as core_router  # noqa: E402
from app.utils.meta import build_meta  # noqa: E402


# Track process start time for uptime calculations
START_TIME = datetime.now(timezone.utc)


app = FastAPI(
    title=settings.version["name"],
    version=settings.version["version"],
)


# Minimal CORS for local + internal use
origins = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:3000",  # common dev frontend
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Simple middleware to log each API call as a JSON line."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        logger.info(
            "API call",
            extra={
                "event_type": "api_call",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
            },
        )
        return response


app.add_middleware(RequestLoggingMiddleware)
app.include_router(core_router)


@app.on_event("startup")
async def on_startup() -> None:
    """Startup hook for Nova core.

    Later we can add DB connections, schedulers, etc.
    """
    app.state.version_info = settings.version
    app.state.start_time = datetime.now(timezone.utc)

    logger.info(
        "Nova startup complete",
        extra={
            "event_type": "startup",
            "env": settings.env,
            "version": settings.version.get("version"),
        },
    )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """Shutdown hook for Nova core.

    Used later for graceful cleanup.
    """
    logger.info("Nova shutdown", extra={"event_type": "shutdown"})


@app.get("/", response_model=BaseResponse)
async def root():
    """Root endpoint: basic Nova status.

    Returns version info + simple online status, wrapped in BaseResponse.
    """
    version = getattr(app.state, "version_info", settings.version)
    meta = build_meta()

    data = {
        "system": version["name"],
        "version": version["version"],
        "build": version["build"],
        "environment": settings.env,
        "status": "online",
    }

    return BaseResponse(
        status="ok",
        data=data,
        meta=meta,
    )


@app.get("/health", response_model=BaseResponse)
async def health(request: Request):
    """Simple health check endpoint with standardized response wrapper.

    Used by Actions, systemd, and dashboards.
    """
    meta = build_meta()

    return BaseResponse(
        status="ok",
        data={"message": "healthy"},
        meta=meta,
    )


@app.get("/status", response_model=BaseResponse)
async def status():
    """Status endpoint with version + uptime + environment.

    This extends the basic health check with richer metadata that other
    systems (telemetry, dashboards, Actions) can consume.
    """
    version = getattr(app.state, "version_info", settings.version)
    start_time = getattr(app.state, "start_time", START_TIME)
    now = datetime.now(timezone.utc)
    uptime_seconds = int((now - start_time).total_seconds())

    meta = build_meta()

    data = {
        "system": version["name"],
        "version": version["version"],
        "build": version["build"],
        "environment": settings.env,
        "status": "online",
        "uptime_seconds": uptime_seconds,
    }

    return BaseResponse(
        status="ok",
        data=data,
        meta=meta,
    )


@app.get("/version", response_model=BaseResponse)
async def version():
    """Version endpoint exposing Nova + schema metadata.

    Pulls from settings.version and app.state.version_info, with safe
    defaults if certain fields are not present yet.
    """
    version_info = getattr(app.state, "version_info", settings.version)
    meta = build_meta()

    data = {
        "nova_version": version_info.get("version", "unknown"),
        "build_date": version_info.get("build_date", "unknown"),
        "api_schema_version": version_info.get("api_schema_version", "v1"),
        "master_doc_version": version_info.get("master_doc_version", "unknown"),
    }

    return BaseResponse(
        status="ok",
        data=data,
        meta=meta,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Global handler for HTTPException.

    Ensures all HTTP errors use the standard ErrorResponse wrapper.
    """
    meta = build_meta()

    error = ErrorInfo(
        code=f"http_{exc.status_code}",
        message=exc.detail or "HTTP error",
    )

    logger.error(
        "HTTP error",
        extra={
            "event_type": "http_error",
            "status_code": exc.status_code,
            "path": request.url.path,
            "detail": exc.detail,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(ErrorResponse(error=error, meta=meta)),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for unexpected exceptions.

    Prevents raw stack traces from leaking to clients and keeps error
    responses consistent.
    """
    meta = build_meta()

    error = ErrorInfo(
        code="internal_error",
        message="An unexpected error occurred.",
    )

    logger.error(
        "Unhandled exception",
        exc_info=True,
        extra={
            "event_type": "unhandled_exception",
            "path": request.url.path,
        },
    )

    return JSONResponse(
        status_code=500,
        content=jsonable_encoder(ErrorResponse(error=error, meta=meta)),
    )