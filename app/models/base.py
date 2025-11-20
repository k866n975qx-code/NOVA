from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class Meta(BaseModel):
    """Standard metadata block attached to all Nova responses."""

    timestamp: datetime
    request_id: Optional[str] = None

    nova_version: Optional[str] = None
    build: Optional[str] = None
    api_schema_version: Optional[str] = None
    master_doc_version: Optional[str] = None

    # You can add more fields later (e.g. node_id, env) without breaking shape.


class BaseResponse(BaseModel):
    """Success response wrapper.

    All normal (non-error) JSON responses should eventually use this.
    """

    status: str = "ok"
    data: Any = None
    meta: Meta


class ErrorInfo(BaseModel):
    """Details about an error condition."""

    code: str
    message: str


class ErrorResponse(BaseModel):
    """Error response wrapper.

    All errors should be returned in this structure so clients can rely on it.
    """

    error: ErrorInfo
    meta: Meta