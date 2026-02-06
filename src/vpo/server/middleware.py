"""API middleware for request validation.

Provides decorators for common validation patterns including
query parameter allowlisting and request body validation.

Usage:
    from vpo.server.middleware import validate_query_params, JOBS_ALLOWED_PARAMS

    @validate_query_params(JOBS_ALLOWED_PARAMS)
    async def api_jobs_handler(request: web.Request) -> web.Response:
        ...
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from functools import wraps

from aiohttp import web

from vpo.server.api.errors import UNKNOWN_PARAMETERS, api_error

logger = logging.getLogger(__name__)

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


def validate_query_params(
    allowed_params: frozenset[str],
    *,
    strict: bool = False,
) -> Callable[[Handler], Handler]:
    """Decorator to validate query parameters against allowlist.

    Args:
        allowed_params: Set of allowed parameter names.
        strict: If True, reject requests with unknown params (400).
                If False, log warning and ignore unknown params.

    Returns:
        Decorator function that validates query params.

    Example:
        @validate_query_params(frozenset({"status", "limit", "offset"}))
        async def api_jobs_handler(request: web.Request) -> web.Response:
            ...
    """

    def decorator(handler: Handler) -> Handler:
        @wraps(handler)
        async def wrapper(request: web.Request) -> web.StreamResponse:
            unknown = set(request.query.keys()) - allowed_params
            if unknown:
                if strict:
                    return api_error(
                        f"Unknown query parameters: {sorted(unknown)}",
                        code=UNKNOWN_PARAMETERS,
                    )
                else:
                    logger.warning(
                        "Ignoring unknown query params in %s: %s",
                        request.path,
                        sorted(unknown),
                    )
            return await handler(request)

        return wrapper

    return decorator


# Allowed query parameters per endpoint group
# These are frozen sets to prevent accidental modification

JOBS_ALLOWED_PARAMS = frozenset(
    {
        "status",
        "type",
        "since",
        "search",
        "sort",
        "order",
        "limit",
        "offset",
    }
)

LIBRARY_ALLOWED_PARAMS = frozenset(
    {
        "status",
        "limit",
        "offset",
        "search",
        "resolution",
        "audio_lang",
        "subtitles",
        "sort",
        "order",
    }
)

PLANS_ALLOWED_PARAMS = frozenset(
    {
        "status",
        "since",
        "policy_name",
        "limit",
        "offset",
    }
)

TRANSCRIPTIONS_ALLOWED_PARAMS = frozenset(
    {
        "show_all",
        "limit",
        "offset",
    }
)

STATS_ALLOWED_PARAMS = frozenset(
    {
        "since",
        "until",
        "policy",
        "limit",
        "group_by",
    }
)

STATS_PURGE_ALLOWED_PARAMS = frozenset(
    {
        "before",
        "policy",
        "all",
        "dry_run",
    }
)
