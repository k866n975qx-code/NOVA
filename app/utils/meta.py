

from datetime import datetime, timezone
from typing import Optional

from app.config.settings import settings
from app.models.base import Meta


def build_meta(
    request_id: Optional[str] = None,
) -> Meta:
    """Construct a standard Meta object for Nova responses.

    This centralizes how we attach version and environment information to
    responses so all endpoints stay consistent.
    """
    now = datetime.now(timezone.utc)
    version = settings.version

    return Meta(
        timestamp=now,
        request_id=request_id,
        nova_version=version.get("version"),
        build=version.get("build"),
        api_schema_version=version.get("api_schema_version"),
        master_doc_version=version.get("master_doc_version"),
    )