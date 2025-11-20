from datetime import datetime, timezone

from fastapi import APIRouter, Request

from app.config.settings import settings
from app.models.base import BaseResponse, Meta
from app.utils.logging_config import get_logger
from app.utils.meta import build_meta


router = APIRouter(tags=["core"])
logger = get_logger("nova.actions")


@router.get("/actions/handshake", response_model=BaseResponse)
async def actions_handshake(request: Request) -> BaseResponse:
    """Handshake endpoint for Nova Actions integration.

    Returns Nova/Doc version info and supported high-level domains so that
    external tools (like ChatGPT Actions) can understand what Nova can do.
    """
    version = settings.version

    meta = build_meta()

    data = {
        "nova_version": version.get("version"),
        "master_doc_version": version.get("master_doc_version", "unknown"),
        "supported_domains": [
            "finance",
            "health",
            "training",
            "protocols",
            "automation",
            "system",
        ],
    }

    logger.info(
        "Actions handshake",
        extra={
            "event_type": "actions_handshake",
            "path": str(request.url.path),
        },
    )

    return BaseResponse(status="ok", data=data, meta=meta)