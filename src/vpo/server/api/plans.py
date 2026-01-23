"""API handlers for plan endpoints.

Endpoints:
    GET /api/plans - List plans with filtering
    POST /api/plans/{plan_id}/approve - Approve a pending plan
    POST /api/plans/{plan_id}/reject - Reject a pending plan
"""

from __future__ import annotations

import asyncio

from aiohttp import web

from vpo.core.datetime_utils import parse_time_filter
from vpo.core.validation import is_valid_uuid
from vpo.server.middleware import PLANS_ALLOWED_PARAMS, validate_query_params
from vpo.server.ui.models import (
    PlanActionResponse,
    PlanDetailItem,
    PlanFilterParams,
    PlanListItem,
    PlanListResponse,
)
from vpo.server.ui.routes import (
    database_required_middleware,
    shutdown_check_middleware,
)


@shutdown_check_middleware
@database_required_middleware
@validate_query_params(PLANS_ALLOWED_PARAMS)
async def api_plans_handler(request: web.Request) -> web.Response:
    """Handle GET /api/plans - JSON API for plans listing.

    Query parameters:
        status: Filter by plan status (pending, approved, rejected, applied, canceled)
        since: Time filter (24h, 7d, 30d)
        policy_name: Filter by policy name
        limit: Page size (1-100, default 50)
        offset: Pagination offset (default 0)

    Returns:
        JSON response with PlanListResponse payload.
    """
    from vpo.db import PlanStatus
    from vpo.db.operations import get_plans_filtered

    # Parse query parameters
    params = PlanFilterParams.from_query(dict(request.query))

    # Validate status parameter
    status_enum = None
    if params.status:
        try:
            status_enum = PlanStatus(params.status)
        except ValueError:
            return web.json_response(
                {"error": f"Invalid status value: '{params.status}'"},
                status=400,
            )

    # Parse time filter (returns None for invalid values)
    since_timestamp = parse_time_filter(params.since)
    if params.since and since_timestamp is None:
        return web.json_response(
            {"error": f"Invalid since value: '{params.since}'"},
            status=400,
        )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query plans from database using thread-safe connection access
    def _query_plans() -> tuple[list, int]:
        with connection_pool.transaction() as conn:
            plans, total = get_plans_filtered(
                conn,
                status=status_enum,
                since=since_timestamp,
                policy_name=params.policy_name,
                limit=params.limit,
                offset=params.offset,
                return_total=True,
            )
            return plans, total

    plans_data, total = await asyncio.to_thread(_query_plans)

    # Convert to PlanListItem
    plan_items = [PlanListItem.from_plan_record(p) for p in plans_data]

    # Determine if any filters are active
    has_filters = bool(params.status or params.since or params.policy_name)

    response = PlanListResponse(
        plans=plan_items,
        total=total,
        limit=params.limit,
        offset=params.offset,
        has_filters=has_filters,
    )

    return web.json_response(response.to_dict())


@shutdown_check_middleware
@database_required_middleware
async def api_plan_detail_handler(request: web.Request) -> web.Response:
    """Handle GET /api/plans/{plan_id} - JSON API for single plan detail.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with PlanDetailItem payload or error.
    """
    from vpo.db.operations import get_plan_by_id

    plan_id = request.match_info["plan_id"]

    # Validate UUID format
    if not is_valid_uuid(plan_id):
        return web.json_response(
            {"error": "Invalid plan ID format"},
            status=400,
        )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query plan from database
    def _query_plan():
        with connection_pool.transaction() as conn:
            return get_plan_by_id(conn, plan_id)

    plan = await asyncio.to_thread(_query_plan)

    if plan is None:
        return web.json_response(
            {"error": "Plan not found"},
            status=404,
        )

    # Convert to detail item with deserialized actions
    detail_item = PlanDetailItem.from_plan_record(plan)

    return web.json_response(detail_item.to_dict())


@shutdown_check_middleware
@database_required_middleware
async def api_plan_approve_handler(request: web.Request) -> web.Response:
    """Handle POST /api/plans/{plan_id}/approve - Approve a pending plan.

    Creates an APPLY job with priority=10 to execute the plan's actions.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with PlanActionResponse payload including job_id and job_url.
    """
    from vpo.jobs.services import PlanApprovalService

    plan_id = request.match_info["plan_id"]

    # Validate UUID format
    if not is_valid_uuid(plan_id):
        return web.json_response(
            PlanActionResponse(success=False, error="Invalid plan ID format").to_dict(),
            status=400,
        )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Use service to approve plan
    service = PlanApprovalService()

    def _approve():
        with connection_pool.transaction() as conn:
            return service.approve(conn, plan_id)

    result = await asyncio.to_thread(_approve)

    if not result.success:
        status_code = 404 if result.error == "Plan not found" else 409
        return web.json_response(
            PlanActionResponse(success=False, error=result.error).to_dict(),
            status=status_code,
        )

    # Build job URL
    job_url = f"/jobs/{result.job_id}"

    response = PlanActionResponse(
        success=True,
        plan=PlanListItem.from_plan_record(result.plan),
        job_id=result.job_id,
        job_url=job_url,
        warning=result.warning,
    )
    return web.json_response(response.to_dict())


@shutdown_check_middleware
@database_required_middleware
async def api_plan_reject_handler(request: web.Request) -> web.Response:
    """Handle POST /api/plans/{plan_id}/reject - Reject a pending plan.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with PlanActionResponse payload.
    """
    from vpo.jobs.services import PlanApprovalService

    plan_id = request.match_info["plan_id"]

    # Validate UUID format
    if not is_valid_uuid(plan_id):
        return web.json_response(
            PlanActionResponse(success=False, error="Invalid plan ID format").to_dict(),
            status=400,
        )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Use service to reject plan
    service = PlanApprovalService()

    def _reject():
        with connection_pool.transaction() as conn:
            return service.reject(conn, plan_id)

    result = await asyncio.to_thread(_reject)

    if not result.success:
        status_code = 404 if result.error == "Plan not found" else 409
        return web.json_response(
            PlanActionResponse(success=False, error=result.error).to_dict(),
            status=status_code,
        )

    response = PlanActionResponse(
        success=True,
        plan=PlanListItem.from_plan_record(result.plan),
    )
    return web.json_response(response.to_dict())


def setup_plan_routes(app: web.Application) -> None:
    """Register plan API routes with the application.

    Args:
        app: aiohttp Application to configure.
    """
    # Plans list routes (026-plans-list-view)
    app.router.add_get("/api/plans", api_plans_handler)
    app.router.add_get("/api/plans/{plan_id}", api_plan_detail_handler)
    app.router.add_post("/api/plans/{plan_id}/approve", api_plan_approve_handler)
    app.router.add_post("/api/plans/{plan_id}/reject", api_plan_reject_handler)
