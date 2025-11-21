

"""
Database engine and session helpers for Nova.

Phase 2.1 — Database Selection & Engine Setup

This module centralizes:
- Reading the database URL from environment variables
- Creating a SQLAlchemy engine with basic connection checks
- Providing a Session factory / dependency helper

Notes:
- We do NOT assume a running database during tests yet.
- We also do NOT import this module from app startup code until
  Phase 2 is further along, to avoid failing hard if Postgres
  is not configured.
"""

import logging
import os
import time
from typing import Generator, Optional

from app.config.settings import settings

try:
    # SQLAlchemy imports are optional at this phase; we fail lazily
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session, sessionmaker
except ImportError:  # pragma: no cover - handled lazily when used
    create_engine = None  # type: ignore[assignment]
    text = None  # type: ignore[assignment]
    Session = None  # type: ignore[assignment]
    sessionmaker = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Cached engine/session factory so we don't rebuild them on every call
_ENGINE = None
_SESSION_LOCAL = None


def get_database_url() -> str:
    """
    Resolve the database URL from settings/environment.

    Priority:
    - settings.database_url (if set)
    - NOVA_DATABASE_URL
    - DATABASE_URL

    Raises:
        RuntimeError: if no database URL is configured.
    """
    # Prefer the centralized settings value when available
    url = getattr(settings, "database_url", None)

    # Fallback to raw environment variables if settings is not populated
    if not url:
        url = os.getenv("NOVA_DATABASE_URL") or os.getenv("DATABASE_URL")

    if not url:
        raise RuntimeError(
            "Database URL not configured. "
            "Set NOVA_DATABASE_URL or DATABASE_URL in your environment."
        )
    return url


def get_engine(max_retries: int = 3, backoff_seconds: float = 1.0):
    """
    Lazily create and return the SQLAlchemy engine.

    - Uses a simple retry mechanism on initial connection.
    - Caches the engine in a module-level variable.

    Raises:
        RuntimeError: if SQLAlchemy is not installed or if the engine
        cannot be initialized after the configured retries.
    """
    global _ENGINE

    if _ENGINE is not None:
        return _ENGINE

    if create_engine is None:
        raise RuntimeError(
            "SQLAlchemy is not installed. Install 'sqlalchemy' to use the database layer."
        )

    db_url = get_database_url()
    last_exc: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            engine = create_engine(db_url, pool_pre_ping=True)

            # Basic connectivity check
            with engine.connect() as conn:
                if text is None:
                    # Extremely defensive fallback; should not happen if SQLAlchemy imported correctly
                    conn.execute("SELECT 1")  # type: ignore[arg-type]
                else:
                    conn.execute(text("SELECT 1"))

            _ENGINE = engine
            logger.info(
                "Database engine initialized",
                extra={
                    "event_type": "db_engine_init",
                    "attempt": attempt,
                },
            )
            return _ENGINE
        except Exception as exc:  # pragma: no cover - behavior verified indirectly later
            last_exc = exc
            logger.warning(
                "Database connection attempt failed",
                extra={
                    "event_type": "db_engine_retry",
                    "attempt": attempt,
                },
            )
            if attempt < max_retries:
                time.sleep(backoff_seconds * attempt)

    raise RuntimeError(
        f"Could not initialize database engine after {max_retries} attempts"
    ) from last_exc


def get_session() -> Generator["Session", None, None]:
    """
    Yield a database session.

    This is written in the FastAPI dependency style (generator pattern)
    so that later we can use:

        Depends(get_session)

    in route handlers, while still being usable in plain service code.

    Raises:
        RuntimeError: if SQLAlchemy is not installed.
    """
    global _SESSION_LOCAL

    if Session is None or sessionmaker is None:
        raise RuntimeError(
            "SQLAlchemy is not installed. Install 'sqlalchemy' to use the database layer."
        )

    engine = get_engine()

    if _SESSION_LOCAL is None:
        _SESSION_LOCAL = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )

    db = _SESSION_LOCAL()
    try:
        yield db
    finally:
        db.close()