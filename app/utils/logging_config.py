import logging
import logging.config
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os
import json
from typing import Any, Dict


# Environment flags (simple for now)
NOVA_ENV = os.getenv("NOVA_ENV", "dev").lower()
NOVA_LOG_LEVEL = os.getenv("NOVA_LOG_LEVEL", "DEBUG").upper()


def get_log_dir() -> Path:
    """
    Decide where logs go based on environment.

    - dev / test:  ./logs
    - prod:        /var/log/nova
    """
    if NOVA_ENV == "prod":
        log_dir = Path("/var/log/nova")
    else:
        log_dir = Path.cwd() / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


class JsonFormatter(logging.Formatter):
    """
    Very simple JSON log formatter.

    Produces lines like:
    {"timestamp": "...", "level": "INFO", "logger": "nova.api", "message": "...", ...}
    """

    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Optional context fields (if provided via logger.extra)
        for key in ("event_type", "path", "method", "status_code"):
            if hasattr(record, key):
                log_record[key] = getattr(record, key)

        # Exception info if present
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(log_record, ensure_ascii=False)


def configure_logging() -> None:
    """
    Configure root logging for Nova.

    - Rotating file handler with JSON logs.
    - Console handler for local dev.
    - Named loggers for errors / ingestion / events / api.
    """
    log_dir = get_log_dir()
    log_file = log_dir / "nova.log"

    log_level = getattr(logging, NOVA_LOG_LEVEL, logging.DEBUG)

    formatter = JsonFormatter()

    # File handler with rotation
    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # Console handler (useful in dev)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    handlers = [file_handler, console_handler]

    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True,  # override any previous basicConfig
    )

    # Optional: create category loggers
    for name in (
        "nova.errors",
        "nova.ingestion",
        "nova.events",
        "nova.api",
    ):
        logging.getLogger(name).setLevel(log_level)


def get_logger(name: str = "nova") -> logging.Logger:
    """
    Helper to get a named Nova logger.
    """
    return logging.getLogger(name)