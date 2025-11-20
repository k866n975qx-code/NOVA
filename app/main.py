from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.logging_config import configure_logging, get_logger

# Configure logging first so all later imports use it
configure_logging()
logger = get_logger("nova.api")

# Import settings AFTER logging is configured
from app.config.settings import settings  # noqa: E402


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
    """
    Simple middleware to log each API call as a JSON line.
    """

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


@app.on_event("startup")
async def on_startup() -> None:
    """
    Startup hook for Nova core.
    Later we can add DB connections, schedulers, etc.
    """
    app.state.version_info = settings.version
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
    """
    Shutdown hook for Nova core.
    Used later for graceful cleanup.
    """
    logger.info("Nova shutdown", extra={"event_type": "shutdown"})


@app.get("/")
async def root():
    """
    Root endpoint: basic Nova status.
    Returns version info + simple online status.
    """
    version = getattr(app.state, "version_info", settings.version)
    return {
        "system": version["name"],
        "version": version["version"],
        "build": version["build"],
        "environment": settings.env,
        "status": "online",
    }


@app.get("/health")
async def health():
    """
    Simple health check endpoint.
    Used by Actions, systemd, and dashboards.
    """
    return {"status": "ok"}