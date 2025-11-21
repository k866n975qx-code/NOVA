from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional


# Root paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
VERSION_FILE = PROJECT_ROOT / "version.json"

# Base defaults
DEFAULTS: Dict[str, str] = {
    "NOVA_ENV": "dev",
    "NOVA_LOG_LEVEL": "DEBUG",
}

# Things that MUST exist in prod (we'll expand this later)
REQUIRED_VARS_PROD = (
    "LUNCHMONEY_API_KEY",  # placeholder for later phases
)

logger = logging.getLogger("nova.config")


def _load_env_file(path: Path) -> Dict[str, str]:
    """
    Very small .env parser.

    Lines like:
        KEY=value
        OTHER="some value"
    """
    data: Dict[str, str] = {}
    if not path.exists():
        return data

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        data[key] = value

    return data


def _build_env() -> Dict[str, str]:
    """
    Build the effective environment with this precedence:

        defaults  <  system env  <  .env

    That means `.env` wins over real environment variables, which
    is what you requested.
    """
    env: Dict[str, str] = dict(DEFAULTS)

    # system env overrides defaults
    keys_of_interest = set(DEFAULTS.keys()) | set(REQUIRED_VARS_PROD) | {
        "LUNCHMONEY_API_KEY",
        "NOVA_ACTIONS_TOKEN",
        "NOVA_DATABASE_URL",
        "DATABASE_URL",
    }
    for key in keys_of_interest:
        if key in os.environ:
            env[key] = os.environ[key]

    # .env overrides both defaults AND system env
    file_env = _load_env_file(ENV_FILE)
    env.update(file_env)

    return env


def _load_version() -> Dict[str, Any]:
    """
    Load version metadata from version.json, with safe fallbacks.
    """
    base: Dict[str, Any] = {
        "name": "Nova Core",
        "version": "0.0.0",
        "build": "unknown",
        "environment": "dev",
        "updated_at": None,
    }

    try:
        with VERSION_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        base.update(data)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to load version.json, using defaults",
            exc_info=exc,
        )

    return base


class Settings:
    """
    Central settings object for Nova.

    - Applies .env > system env > defaults
    - Loads version.json
    - Performs basic validation
    """

    def __init__(self) -> None:
        env = _build_env()

        self.env: str = env.get("NOVA_ENV", "dev").lower()
        self.log_level: str = env.get("NOVA_LOG_LEVEL", "DEBUG").upper()

        # Future integrations (Lunch Money, etc.)
        self.lunchmoney_api_key: Optional[str] = env.get("LUNCHMONEY_API_KEY")
        # Optional Actions API token (for /actions/* auth in later phases)
        self.actions_api_token: Optional[str] = env.get("NOVA_ACTIONS_TOKEN")

        # Optional database URL for PostgreSQL (used by Phase 2 DB layer)
        self.database_url: Optional[str] = env.get("NOVA_DATABASE_URL") or env.get(
            "DATABASE_URL"
        )

        # Version metadata
        self.version: Dict[str, Any] = _load_version()

        # Run validation
        self._validate(env)

    def _validate(self, env: Dict[str, str]) -> None:
        # Log level sanity
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"Invalid NOVA_LOG_LEVEL: {self.log_level}")

        # Required vars in prod
        if self.env == "prod":
            missing = [key for key in REQUIRED_VARS_PROD if not env.get(key)]
            if missing:
                raise RuntimeError(
                    f"Missing required environment variables in prod: {', '.join(missing)}"
                )


# Singleton settings object
settings = Settings()