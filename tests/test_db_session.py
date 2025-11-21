

"""
Tests for the database session helper (Phase 2.1).

These tests focus on get_database_url() behavior:
- Prefer settings.database_url when set
- Fall back to NOVA_DATABASE_URL / DATABASE_URL when settings.database_url is unset
- Raise RuntimeError when no database URL is configured
"""

import os
from typing import Optional

import pytest

from app.config.settings import settings
from app.db.session import get_database_url


def _clear_db_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Helper to ensure DB-related env vars are cleared for each scenario."""
    monkeypatch.delenv("NOVA_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)


def test_get_database_url_prefers_settings_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """If settings.database_url is set, it should be used even if env vars exist."""
    _clear_db_env(monkeypatch)

    # Snapshot original value to restore after test
    original_db_url: Optional[str] = getattr(settings, "database_url", None)

    try:
        # Configure both settings and env to ensure settings takes priority
        monkeypatch.setattr(settings, "database_url", "postgresql://settings-db/test", raising=False)
        monkeypatch.setenv("NOVA_DATABASE_URL", "postgresql://env-nova/test")
        monkeypatch.setenv("DATABASE_URL", "postgresql://env-generic/test")

        url = get_database_url()
        assert url == "postgresql://settings-db/test"
    finally:
        # Restore original settings value
        monkeypatch.setattr(settings, "database_url", original_db_url, raising=False)


def test_get_database_url_falls_back_to_nova_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """If settings.database_url is empty/None, fall back to NOVA_DATABASE_URL when present."""
    _clear_db_env(monkeypatch)

    original_db_url: Optional[str] = getattr(settings, "database_url", None)

    try:
        # Ensure settings.database_url is unset for this scenario
        monkeypatch.setattr(settings, "database_url", None, raising=False)
        monkeypatch.setenv("NOVA_DATABASE_URL", "postgresql://env-nova/test")

        url = get_database_url()
        assert url == "postgresql://env-nova/test"
    finally:
        monkeypatch.setattr(settings, "database_url", original_db_url, raising=False)


def test_get_database_url_falls_back_to_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """If settings.database_url and NOVA_DATABASE_URL are unset, fall back to DATABASE_URL."""
    _clear_db_env(monkeypatch)

    original_db_url: Optional[str] = getattr(settings, "database_url", None)

    try:
        monkeypatch.setattr(settings, "database_url", None, raising=False)
        # Only set DATABASE_URL for this scenario
        monkeypatch.setenv("DATABASE_URL", "postgresql://env-generic/test")

        url = get_database_url()
        assert url == "postgresql://env-generic/test"
    finally:
        monkeypatch.setattr(settings, "database_url", original_db_url, raising=False)


def test_get_database_url_raises_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    """If no DB URL is configured anywhere, get_database_url should raise RuntimeError."""
    _clear_db_env(monkeypatch)

    original_db_url: Optional[str] = getattr(settings, "database_url", None)

    try:
        monkeypatch.setattr(settings, "database_url", None, raising=False)

        with pytest.raises(RuntimeError) as excinfo:
            _ = get_database_url()

        message = str(excinfo.value)
        assert "Database URL not configured" in message
    finally:
        monkeypatch.setattr(settings, "database_url", original_db_url, raising=False)