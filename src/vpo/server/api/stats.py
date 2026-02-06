"""API handlers for processing statistics endpoints.

Endpoints:
    GET /api/stats/summary - Statistics summary
    GET /api/stats/recent - Recent processing history
    GET /api/stats/policies - Per-policy statistics
    GET /api/stats/policies/{name} - Single policy statistics
    GET /api/stats/files/{file_id} - File processing history
    GET /api/stats/{stats_id} - Single stats record detail
    DELETE /api/stats/purge - Delete processing statistics
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict

from aiohttp import web

from vpo.core.datetime_utils import parse_time_filter
from vpo.core.validation import is_valid_uuid
from vpo.db.views import (
    get_policy_stats,
    get_policy_stats_by_name,
    get_recent_stats,
    get_stats_detail,
    get_stats_for_file,
    get_stats_summary,
    get_stats_trends,
)
from vpo.server.api.errors import (
    INVALID_ID_FORMAT,
    INVALID_PARAMETER,
    INVALID_REQUEST,
    NOT_FOUND,
    api_error,
)
from vpo.server.middleware import (
    STATS_ALLOWED_PARAMS,
    STATS_PURGE_ALLOWED_PARAMS,
    validate_query_params,
)
from vpo.server.ui.routes import (
    database_required_middleware,
    shutdown_check_middleware,
)


@shutdown_check_middleware
@database_required_middleware
@validate_query_params(STATS_ALLOWED_PARAMS)
async def api_stats_summary_handler(request: web.Request) -> web.Response:
    """Handle GET /api/stats/summary - JSON API for statistics summary.

    Query parameters:
        since: Time filter (24h, 7d, 30d, or ISO-8601)
        until: Time filter end (ISO-8601)
        policy_name: Filter by policy name

    Returns:
        JSON response with StatsSummary payload.
    """
    # Parse query parameters
    since_str = request.query.get("since")
    until_str = request.query.get("until")
    policy_name = request.query.get("policy")

    # Parse time filters
    since_ts = None
    if since_str:
        since_ts = parse_time_filter(since_str)
        if since_ts is None:
            return api_error(
                f"Invalid since value: '{since_str}'",
                code=INVALID_PARAMETER,
            )

    until_ts = None
    if until_str:
        until_ts = parse_time_filter(until_str)
        if until_ts is None:
            return api_error(
                f"Invalid until value: '{until_str}'",
                code=INVALID_PARAMETER,
            )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query stats summary
    def _query_summary():
        with connection_pool.transaction() as conn:
            return get_stats_summary(
                conn,
                since=since_ts,
                until=until_ts,
                policy_name=policy_name,
            )

    summary = await asyncio.to_thread(_query_summary)

    return web.json_response(asdict(summary))


@shutdown_check_middleware
@database_required_middleware
async def api_stats_recent_handler(request: web.Request) -> web.Response:
    """Handle GET /api/stats/recent - JSON API for recent processing history.

    Query parameters:
        limit: Maximum entries to return (1-100, default 10)
        policy_name: Filter by policy name

    Returns:
        JSON response with list of FileProcessingHistory items.
    """
    # Parse query parameters
    try:
        limit = int(request.query.get("limit", 10))
        limit = max(1, min(100, limit))
    except (ValueError, TypeError):
        limit = 10

    policy_name = request.query.get("policy")

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query recent stats
    def _query_recent():
        with connection_pool.transaction() as conn:
            return get_recent_stats(
                conn,
                limit=limit,
                policy_name=policy_name,
            )

    entries = await asyncio.to_thread(_query_recent)

    return web.json_response([asdict(e) for e in entries])


@shutdown_check_middleware
@database_required_middleware
async def api_stats_policies_handler(request: web.Request) -> web.Response:
    """Handle GET /api/stats/policies - JSON API for per-policy statistics.

    Query parameters:
        since: Time filter (24h, 7d, 30d, or ISO-8601)
        until: Time filter end (ISO-8601)

    Returns:
        JSON response with list of PolicyStats items.
    """
    # Parse query parameters
    since_str = request.query.get("since")
    until_str = request.query.get("until")

    # Parse time filters
    since_ts = None
    if since_str:
        since_ts = parse_time_filter(since_str)
        if since_ts is None:
            return api_error(
                f"Invalid since value: '{since_str}'",
                code=INVALID_PARAMETER,
            )

    until_ts = None
    if until_str:
        until_ts = parse_time_filter(until_str)
        if until_ts is None:
            return api_error(
                f"Invalid until value: '{until_str}'",
                code=INVALID_PARAMETER,
            )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query policy stats
    def _query_policies():
        with connection_pool.transaction() as conn:
            return get_policy_stats(
                conn,
                since=since_ts,
                until=until_ts,
            )

    policies = await asyncio.to_thread(_query_policies)

    return web.json_response([asdict(p) for p in policies])


@shutdown_check_middleware
@database_required_middleware
@validate_query_params(STATS_ALLOWED_PARAMS)
async def api_stats_trends_handler(request: web.Request) -> web.Response:
    """Handle GET /api/stats/trends - JSON API for processing trends.

    Query parameters:
        since: Time filter (24h, 7d, 30d, or ISO-8601)
        group_by: Time grouping: 'day' (default), 'week', or 'month'

    Returns:
        JSON response with list of TrendDataPoint items for charting.
    """
    # Parse query parameters
    since_str = request.query.get("since")
    group_by = request.query.get("group_by", "day")

    # Validate group_by
    if group_by not in ("day", "week", "month"):
        return api_error(
            f"Invalid group_by value: '{group_by}'. Must be 'day', 'week', or 'month'.",
            code=INVALID_PARAMETER,
        )

    # Parse time filters
    since_ts = None
    if since_str:
        since_ts = parse_time_filter(since_str)
        if since_ts is None:
            return api_error(
                f"Invalid since value: '{since_str}'",
                code=INVALID_PARAMETER,
            )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query trends
    def _query_trends():
        with connection_pool.transaction() as conn:
            return get_stats_trends(
                conn,
                since=since_ts,
                group_by=group_by,
            )

    trends = await asyncio.to_thread(_query_trends)

    return web.json_response([asdict(t) for t in trends])


@database_required_middleware
async def api_stats_detail_handler(request: web.Request) -> web.Response:
    """Handle GET /api/stats/{stats_id} - JSON API for single stats record detail.

    Path parameters:
        stats_id: UUID of the processing_stats record.

    Returns:
        JSON response with full StatsDetailView including actions.
    """
    stats_id = request.match_info.get("stats_id")
    if not stats_id or not is_valid_uuid(stats_id):
        return api_error("Invalid stats_id", code=INVALID_ID_FORMAT)

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    def _query_detail():
        with connection_pool.transaction() as conn:
            return get_stats_detail(conn, stats_id)

    detail = await asyncio.to_thread(_query_detail)

    if detail is None:
        return api_error(
            f"Stats record not found: {stats_id}",
            code=NOT_FOUND,
            status=404,
        )

    return web.json_response(asdict(detail))


@database_required_middleware
async def api_stats_file_handler(request: web.Request) -> web.Response:
    """Handle GET /api/stats/files/{file_id} - JSON API for file processing history.

    Path parameters:
        file_id: ID of the file to get history for.

    Returns:
        JSON response with list of FileProcessingHistory items.
    """
    file_id_str = request.match_info.get("file_id")
    if not file_id_str:
        return api_error("file_id is required", code=INVALID_REQUEST)

    try:
        file_id = int(file_id_str)
    except ValueError:
        return api_error("file_id must be an integer", code=INVALID_ID_FORMAT)

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    def _query_file_stats():
        with connection_pool.transaction() as conn:
            return get_stats_for_file(conn, file_id=file_id)

    history = await asyncio.to_thread(_query_file_stats)

    return web.json_response([asdict(h) for h in history])


@shutdown_check_middleware
@database_required_middleware
@validate_query_params(STATS_PURGE_ALLOWED_PARAMS)
async def api_stats_purge_handler(request: web.Request) -> web.Response:
    """Handle DELETE /api/stats/purge - Delete processing statistics.

    Query parameters:
        before: Delete stats older than (relative: 30d, 90d or ISO-8601)
        policy: Delete stats for a specific policy name
        all: Delete ALL statistics (requires confirmation)
        dry_run: Preview what would be deleted without making changes

    Returns:
        JSON response with purge result (deleted count or error).
    """
    from vpo.db.queries import (
        delete_all_processing_stats,
        delete_processing_stats_before,
        delete_processing_stats_by_policy,
    )

    # Parse query parameters
    before_str = request.query.get("before")
    policy_name = request.query.get("policy")
    delete_all = request.query.get("all", "").casefold() in ("true", "1", "yes")
    dry_run = request.query.get("dry_run", "").casefold() in ("true", "1", "yes")

    # Validate options
    if not before_str and not policy_name and not delete_all:
        return api_error(
            "Must specify at least one of: before, policy, or all",
            code=INVALID_REQUEST,
        )

    if delete_all and (before_str or policy_name):
        return api_error(
            "all cannot be combined with before or policy",
            code=INVALID_REQUEST,
        )

    if before_str and policy_name:
        return api_error(
            "before and policy cannot be combined. Use separate requests.",
            code=INVALID_REQUEST,
        )

    # Parse time filter if provided
    before_ts = None
    if before_str:
        before_ts = parse_time_filter(before_str)
        if before_ts is None:
            return api_error(
                f"Invalid before value: '{before_str}'",
                code=INVALID_PARAMETER,
            )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Execute purge
    def _execute_purge() -> int:
        with connection_pool.transaction() as conn:
            if delete_all:
                return delete_all_processing_stats(conn, dry_run=dry_run)
            elif before_ts:
                return delete_processing_stats_before(conn, before_ts, dry_run=dry_run)
            else:
                return delete_processing_stats_by_policy(
                    conn,
                    policy_name,
                    dry_run=dry_run,  # type: ignore
                )

    deleted = await asyncio.to_thread(_execute_purge)

    # Build description
    if delete_all:
        target = "all processing statistics"
    elif before_ts:
        target = f"stats older than {before_str}"
    else:
        target = f"stats for policy '{policy_name}'"

    if dry_run:
        return web.json_response(
            {
                "dry_run": True,
                "would_delete": deleted,
                "target": target,
            }
        )
    else:
        return web.json_response(
            {
                "deleted": deleted,
                "target": target,
            }
        )


@database_required_middleware
async def api_stats_policy_handler(request: web.Request) -> web.Response:
    """Handle GET /api/stats/policies/{name} - JSON API for single policy stats.

    Path parameters:
        name: Name of the policy to get stats for.

    Query parameters:
        since: Time filter (24h, 7d, 30d, or ISO-8601)
        until: Time filter end (ISO-8601)

    Returns:
        JSON response with PolicyStats for the policy.
    """
    policy_name = request.match_info.get("name")
    if not policy_name:
        return api_error("Policy name is required", code=INVALID_REQUEST)

    # Parse query parameters
    since_str = request.query.get("since")
    until_str = request.query.get("until")

    # Parse time filters
    since_ts = None
    if since_str:
        since_ts = parse_time_filter(since_str)
        if since_ts is None:
            return api_error(
                f"Invalid since value: '{since_str}'",
                code=INVALID_PARAMETER,
            )

    until_ts = None
    if until_str:
        until_ts = parse_time_filter(until_str)
        if until_ts is None:
            return api_error(
                f"Invalid until value: '{until_str}'",
                code=INVALID_PARAMETER,
            )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    def _query_policy():
        with connection_pool.transaction() as conn:
            return get_policy_stats_by_name(
                conn,
                policy_name,
                since=since_ts,
                until=until_ts,
            )

    policy = await asyncio.to_thread(_query_policy)

    if policy is None:
        return api_error(
            f"No statistics found for policy: {policy_name}",
            code=NOT_FOUND,
            status=404,
        )

    return web.json_response(asdict(policy))


@shutdown_check_middleware
@database_required_middleware
@validate_query_params(frozenset())
async def api_library_distribution_handler(
    request: web.Request,
) -> web.Response:
    """Handle GET /api/stats/library-distribution.

    Returns distribution of container formats, video codecs, and audio codecs
    across the library for pie chart rendering.

    No query parameters (reflects current library state).

    Returns:
        JSON response with containers, video_codecs, audio_codecs lists.
    """
    from vpo.db.views import get_library_distribution

    connection_pool = request["connection_pool"]

    def _query():
        with connection_pool.transaction() as conn:
            return get_library_distribution(conn)

    distribution = await asyncio.to_thread(_query)

    return web.json_response(asdict(distribution))


LIBRARY_TRENDS_ALLOWED_PARAMS = frozenset({"since"})


@shutdown_check_middleware
@database_required_middleware
@validate_query_params(LIBRARY_TRENDS_ALLOWED_PARAMS)
async def api_library_trends_handler(
    request: web.Request,
) -> web.Response:
    """Handle GET /api/stats/library-trends.

    Returns library snapshot data for charting file counts and sizes
    over time.

    Query parameters:
        since: Time filter (7d, 30d, 90d, or ISO-8601)

    Returns:
        JSON array of snapshot points.
    """
    from vpo.db.views import get_library_snapshots

    since_str = request.query.get("since")
    since_ts = None
    if since_str:
        since_ts = parse_time_filter(since_str)
        if since_ts is None:
            return api_error(
                f"Invalid since value: '{since_str}'",
                code=INVALID_PARAMETER,
            )

    connection_pool = request["connection_pool"]

    def _query():
        with connection_pool.transaction() as conn:
            return get_library_snapshots(conn, since=since_ts)

    snapshots = await asyncio.to_thread(_query)

    return web.json_response([asdict(s) for s in snapshots])


def get_stats_routes() -> list[tuple[str, str, object]]:
    """Return stats API route definitions as (method, path_suffix, handler) tuples.

    Note: Named routes (/policies/{name}, /files/{file_id}, /{stats_id})
    must come after fixed routes to avoid matching conflicts.
    """
    return [
        ("GET", "/stats/summary", api_stats_summary_handler),
        ("GET", "/stats/recent", api_stats_recent_handler),
        ("GET", "/stats/trends", api_stats_trends_handler),
        ("GET", "/stats/library-trends", api_library_trends_handler),
        ("GET", "/stats/library-distribution", api_library_distribution_handler),
        ("GET", "/stats/policies", api_stats_policies_handler),
        ("GET", "/stats/policies/{name}", api_stats_policy_handler),
        ("GET", "/stats/files/{file_id}", api_stats_file_handler),
        ("GET", "/stats/{stats_id}", api_stats_detail_handler),
        ("DELETE", "/stats/purge", api_stats_purge_handler),
    ]


def setup_stats_routes(app: web.Application) -> None:
    """Register stats API routes with the application.

    Args:
        app: aiohttp Application to configure.
    """
    for method, suffix, handler in get_stats_routes():
        app.router.add_route(method, f"/api{suffix}", handler)
