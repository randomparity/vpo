"""HTTP Basic Authentication middleware for VPO web UI.

This module provides minimal authentication for protecting the VPO web UI
and API endpoints. It uses HTTP Basic Authentication (RFC 7617) with a
shared token configured via environment variable or config file.

Security note: This is minimal authentication suitable for localhost/LAN use.
For production deployments over the internet, use a reverse proxy with TLS
and proper authentication.
"""

from __future__ import annotations

import base64
import logging
import secrets
from collections.abc import Callable
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from aiohttp.web import Request, StreamResponse

logger = logging.getLogger(__name__)

# Type alias for aiohttp request handlers
RequestHandler = Callable[[Request], StreamResponse]


def parse_basic_auth(auth_header: str | None) -> tuple[str, str] | None:
    """Parse HTTP Basic Authentication header.

    Args:
        auth_header: The value of the Authorization header, or None.

    Returns:
        Tuple of (username, password) if valid Basic auth header,
        None if header is missing, malformed, or not Basic auth.

    Example:
        >>> parse_basic_auth("Basic dXNlcjpwYXNzd29yZA==")
        ('user', 'password')
        >>> parse_basic_auth("Bearer token123")
        None
        >>> parse_basic_auth(None)
        None
    """
    if not auth_header or not auth_header.startswith("Basic "):
        return None

    try:
        # Extract base64-encoded credentials after "Basic "
        encoded = auth_header[6:]
        decoded = base64.b64decode(encoded).decode("utf-8")

        # Split on first colon only (password may contain colons)
        if ":" not in decoded:
            return None

        username, password = decoded.split(":", 1)
        return (username, password)
    except (ValueError, UnicodeDecodeError):
        return None


def validate_token(provided: str, expected: str) -> bool:
    """Validate provided token against expected token using constant-time comparison.

    Uses secrets.compare_digest to prevent timing attacks.

    Args:
        provided: The token provided by the user.
        expected: The expected/configured token.

    Returns:
        True if tokens match, False otherwise.
    """
    # Encode to bytes for compare_digest
    return secrets.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def is_auth_enabled(token: str | None) -> bool:
    """Check if authentication is enabled based on token configuration.

    Args:
        token: The configured auth token, or None.

    Returns:
        True if auth is enabled (token is non-empty), False otherwise.
        Empty string or whitespace-only is treated as disabled.
    """
    return token is not None and token.strip() != ""


def create_auth_middleware(
    auth_token: str,
) -> Callable[[Request, RequestHandler], StreamResponse]:
    """Create auth middleware for the given token.

    The returned middleware:
    - Allows /health endpoint without authentication (for load balancers)
    - Requires valid Basic Auth credentials for all other endpoints
    - Returns 401 with WWW-Authenticate header on auth failure

    Args:
        auth_token: The shared secret token to validate against.

    Returns:
        aiohttp middleware function.
    """

    @web.middleware
    async def auth_middleware(
        request: web.Request, handler: RequestHandler
    ) -> web.StreamResponse:
        """Authenticate requests using HTTP Basic Auth."""
        # Skip auth for health endpoint (load balancer probes)
        if request.path == "/health":
            return await handler(request)

        # Check Authorization header
        auth_header = request.headers.get("Authorization")
        credentials = parse_basic_auth(auth_header)

        if credentials is None:
            # No credentials or invalid format
            return web.Response(
                status=401,
                text="Unauthorized",
                headers={"WWW-Authenticate": 'Basic realm="VPO"'},
            )

        _username, password = credentials

        # Validate token (password field contains the token)
        if not validate_token(password, auth_token):
            return web.Response(
                status=401,
                text="Unauthorized",
                headers={"WWW-Authenticate": 'Basic realm="VPO"'},
            )

        # Auth successful, proceed to handler
        return await handler(request)

    return auth_middleware
