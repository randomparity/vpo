"""Standardized API error response helper.

Provides a consistent error response format with machine-readable error codes
for all API endpoints. All error responses include:
- ``error``: Human-readable error message
- ``code``: Machine-readable error code string
- ``details`` (optional): Additional context for the error

Usage:
    from vpo.server.api.errors import api_error, INVALID_REQUEST

    return api_error("Name is required", code=INVALID_REQUEST)
"""

from __future__ import annotations

from typing import Any

from aiohttp import web

# --- Error code constants ---

INVALID_REQUEST = "INVALID_REQUEST"
INVALID_JSON = "INVALID_JSON"
NOT_FOUND = "NOT_FOUND"
SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
INVALID_PARAMETER = "INVALID_PARAMETER"
UNKNOWN_PARAMETERS = "UNKNOWN_PARAMETERS"
VALIDATION_FAILED = "VALIDATION_FAILED"
INVALID_ID_FORMAT = "INVALID_ID_FORMAT"
CONCURRENT_MODIFICATION = "CONCURRENT_MODIFICATION"
RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
BATCH_SIZE_EXCEEDED = "BATCH_SIZE_EXCEEDED"
INTERNAL_ERROR = "INTERNAL_ERROR"
SHUTTING_DOWN = "SHUTTING_DOWN"
DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
CSRF_ERROR = "CSRF_ERROR"
RATE_LIMITED = "RATE_LIMITED"


def api_error(
    message: str,
    *,
    code: str,
    status: int = 400,
    details: Any = None,
) -> web.Response:
    """Create a standardized JSON error response.

    Args:
        message: Human-readable error description.
        code: Machine-readable error code (use constants from this module).
        status: HTTP status code (default 400).
        details: Optional additional context (string, list, or dict).

    Returns:
        aiohttp JSON response with ``{"error": ..., "code": ...}`` body.
    """
    body: dict[str, Any] = {"error": message, "code": code}
    if details is not None:
        body["details"] = details
    return web.json_response(body, status=status)
