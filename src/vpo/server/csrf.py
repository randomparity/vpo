"""CSRF protection middleware for VPO web UI.

This module provides CSRF (Cross-Site Request Forgery) protection for
state-changing operations in the VPO web interface.
"""

import logging
import secrets
from collections.abc import Awaitable, Callable

from aiohttp import web
from aiohttp_session import get_session

logger = logging.getLogger(__name__)

# CSRF token header name
CSRF_HEADER = "X-CSRF-Token"

# Session key for CSRF token
CSRF_SESSION_KEY = "csrf_token"


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token.

    Returns:
        A random 32-character hexadecimal string.
    """
    return secrets.token_hex(32)


async def get_csrf_token(request: web.Request) -> str:
    """Get or create CSRF token for the current session.

    Args:
        request: aiohttp Request object.

    Returns:
        CSRF token from session, or newly generated token if none exists.
    """
    session = await get_session(request)
    token = session.get(CSRF_SESSION_KEY)

    if not token:
        token = generate_csrf_token()
        session[CSRF_SESSION_KEY] = token
        logger.debug("Generated new CSRF token for session")

    return token


@web.middleware
async def csrf_middleware(
    request: web.Request, handler: Callable[[web.Request], Awaitable[web.Response]]
) -> web.Response:
    """CSRF protection middleware.

    For GET/HEAD/OPTIONS requests: Retrieves or generates CSRF token and stores
    it in request context for templates to access.

    For POST/PUT/DELETE/PATCH requests: Validates CSRF token from request header
    against session token. Returns 403 Forbidden if validation fails.

    Args:
        request: aiohttp Request object.
        handler: Next handler in the middleware chain.

    Returns:
        Response from handler, or 403 Forbidden if CSRF validation fails.
    """
    # Safe methods don't need CSRF protection
    if request.method in ("GET", "HEAD", "OPTIONS"):
        # Get or generate token for safe requests
        token = await get_csrf_token(request)
        # Store in request context for templates
        request["csrf_token"] = token
        return await handler(request)

    # State-changing methods require CSRF validation
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        # Get session token
        session = await get_session(request)
        session_token = session.get(CSRF_SESSION_KEY)

        if not session_token:
            logger.warning(
                "CSRF validation failed: no session token",
                extra={"method": request.method, "path": request.path},
            )
            return web.json_response(
                {"error": "CSRF token missing from session"},
                status=403,
            )

        # Get token from request header
        request_token = request.headers.get(CSRF_HEADER)

        if not request_token:
            logger.warning(
                "CSRF validation failed: no token in request",
                extra={"method": request.method, "path": request.path},
            )
            return web.json_response(
                {"error": f"CSRF token required in {CSRF_HEADER} header"},
                status=403,
            )

        # Validate token using timing-safe comparison
        if not secrets.compare_digest(request_token, session_token):
            logger.warning(
                "CSRF validation failed: token mismatch",
                extra={"method": request.method, "path": request.path},
            )
            return web.json_response(
                {"error": "Invalid CSRF token"},
                status=403,
            )

        # Store validated token in request context
        request["csrf_token"] = session_token

    return await handler(request)
