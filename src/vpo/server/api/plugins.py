"""API handlers for plugin data browser endpoints.

Endpoints:
    GET /api/plugins - List registered plugins
    GET /api/plugins/{name}/files - Files with data from plugin
    GET /api/files/{file_id}/plugin-data - All plugin data for file
    GET /api/files/{file_id}/plugin-data/{plugin} - Single plugin's data for file
"""

from __future__ import annotations

import asyncio
import logging
import re

from aiohttp import web

from vpo.db.connection import DaemonConnectionPool
from vpo.server.ui.models import (
    FilePluginDataResponse,
    PluginFileItem,
    PluginFilesResponse,
    PluginInfo,
    PluginListResponse,
)
from vpo.server.ui.routes import (
    database_required_middleware,
    shutdown_check_middleware,
)

logger = logging.getLogger(__name__)


def _make_file_plugin_query(connection_pool: DaemonConnectionPool, file_id: int):
    """Create a callable that queries file record and plugin data.

    Returns a function suitable for asyncio.to_thread() that returns
    (FileRecord | None, dict) tuple.

    Args:
        connection_pool: Database connection pool.
        file_id: ID of file to query.

    Returns:
        Callable that returns (file_record, plugin_data) tuple.
    """
    from vpo.db import get_file_by_id
    from vpo.db.views import get_plugin_data_for_file

    def _query():
        with connection_pool.transaction() as conn:
            file_record = get_file_by_id(conn, file_id)
            if file_record is None:
                return None, {}
            plugin_data = get_plugin_data_for_file(conn, file_id)
            return file_record, plugin_data

    return _query


@shutdown_check_middleware
async def api_plugins_list_handler(request: web.Request) -> web.Response:
    """Handle GET /api/plugins - JSON API for registered plugins list.

    Returns:
        JSON response with PluginListResponse payload.
    """
    from vpo.plugin.manifest import PluginSource

    # Get plugin registry from app context
    registry = request.app.get("plugin_registry")
    if registry is None:
        # No registry configured - return empty list
        response = PluginListResponse(plugins=[], total=0)
        return web.json_response(response.to_dict())

    # Get all loaded plugins
    loaded_plugins = registry.get_all()

    # Build plugin info with defensive error handling
    plugins = []
    for p in loaded_plugins:
        try:
            plugins.append(
                PluginInfo(
                    name=p.name,
                    version=p.version,
                    enabled=p.enabled,
                    is_builtin=p.source == PluginSource.BUILTIN,
                    events=p.events,
                )
            )
        except AttributeError as e:
            logger.warning("Skipping malformed plugin: %s", e)

    response = PluginListResponse(plugins=plugins, total=len(plugins))
    return web.json_response(response.to_dict())


@shutdown_check_middleware
@database_required_middleware
async def api_plugin_files_handler(request: web.Request) -> web.Response:
    """Handle GET /api/plugins/{name}/files - Files with data from plugin.

    Path parameters:
        name: Plugin identifier (e.g., "whisper-transcriber").

    Query parameters:
        limit: Page size (1-100, default 50).
        offset: Pagination offset (default 0).

    Returns:
        JSON response with PluginFilesResponse payload.
    """
    from vpo.db.views import get_files_with_plugin_data

    plugin_name = request.match_info["name"]

    # Validate plugin name (alphanumeric, dash, underscore only)
    if not re.match(r"^[a-zA-Z0-9_-]+$", plugin_name):
        return web.json_response(
            {"error": "Invalid plugin name format"},
            status=400,
        )

    # Parse pagination parameters
    try:
        limit = int(request.query.get("limit", 50))
        limit = max(1, min(100, limit))
    except (ValueError, TypeError):
        limit = 50

    try:
        offset = int(request.query.get("offset", 0))
        offset = max(0, offset)
    except (ValueError, TypeError):
        offset = 0

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query files from database
    def _query_files() -> tuple[list[dict], int]:
        with connection_pool.transaction() as conn:
            result = get_files_with_plugin_data(
                conn,
                plugin_name,
                limit=limit,
                offset=offset,
                return_total=True,
            )
            return result  # type: ignore[return-value]

    files_data, total = await asyncio.to_thread(_query_files)

    # Convert to PluginFileItem
    files = [
        PluginFileItem(
            id=f["id"],
            filename=f["filename"],
            path=f["path"],
            scan_status=f["scan_status"],
            plugin_data=f["plugin_data"],
        )
        for f in files_data
    ]

    response = PluginFilesResponse(
        plugin_name=plugin_name,
        files=files,
        total=total,
        limit=limit,
        offset=offset,
    )

    return web.json_response(response.to_dict())


@shutdown_check_middleware
@database_required_middleware
async def api_file_plugin_data_handler(request: web.Request) -> web.Response:
    """Handle GET /api/files/{file_id}/plugin-data - All plugin data for file.

    Path parameters:
        file_id: ID of file to get plugin data for.

    Returns:
        JSON response with FilePluginDataResponse payload.
    """
    file_id_str = request.match_info["file_id"]

    # Validate ID format (integer)
    try:
        file_id = int(file_id_str)
        if file_id < 1:
            raise ValueError("Invalid ID")
    except ValueError:
        return web.json_response(
            {"error": "Invalid file ID format"},
            status=400,
        )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query file and plugin data
    query_fn = _make_file_plugin_query(connection_pool, file_id)
    file_record, plugin_data = await asyncio.to_thread(query_fn)

    if file_record is None:
        return web.json_response(
            {"error": "File not found"},
            status=404,
        )

    response = FilePluginDataResponse(
        file_id=file_id,
        filename=file_record.filename,
        plugin_data=plugin_data,
    )

    return web.json_response(response.to_dict())


@shutdown_check_middleware
@database_required_middleware
async def api_file_plugin_data_single_handler(request: web.Request) -> web.Response:
    """Handle GET /api/files/{file_id}/plugin-data/{plugin} - Single plugin's data.

    Path parameters:
        file_id: ID of file to get plugin data for.
        plugin: Plugin identifier.

    Returns:
        JSON response with plugin-specific data.
    """
    file_id_str = request.match_info["file_id"]
    plugin_name = request.match_info["plugin"]

    # Validate ID format (integer)
    try:
        file_id = int(file_id_str)
        if file_id < 1:
            raise ValueError("Invalid ID")
    except ValueError:
        return web.json_response(
            {"error": "Invalid file ID format"},
            status=400,
        )

    # Validate plugin name
    if not re.match(r"^[a-zA-Z0-9_-]+$", plugin_name):
        return web.json_response(
            {"error": "Invalid plugin name format"},
            status=400,
        )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query file and plugin data
    query_fn = _make_file_plugin_query(connection_pool, file_id)
    file_record, plugin_data = await asyncio.to_thread(query_fn)

    if file_record is None:
        return web.json_response(
            {"error": "File not found"},
            status=404,
        )

    # Get specific plugin's data
    specific_data = plugin_data.get(plugin_name)
    if specific_data is None:
        return web.json_response(
            {"error": f"No data from plugin '{plugin_name}' for this file"},
            status=404,
        )

    return web.json_response(
        {
            "file_id": file_id,
            "filename": file_record.filename,
            "plugin_name": plugin_name,
            "data": specific_data,
        }
    )


def setup_plugin_routes(app: web.Application) -> None:
    """Register plugin API routes with the application.

    Args:
        app: aiohttp Application to configure.
    """
    # Plugin data browser API routes (236-generic-plugin-data-browser)
    app.router.add_get("/api/plugins", api_plugins_list_handler)
    app.router.add_get("/api/plugins/{name}/files", api_plugin_files_handler)
    app.router.add_get("/api/files/{file_id}/plugin-data", api_file_plugin_data_handler)
    app.router.add_get(
        "/api/files/{file_id}/plugin-data/{plugin}", api_file_plugin_data_single_handler
    )
