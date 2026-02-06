"""API handlers for library file and transcription endpoints.

Endpoints:
    GET /api/library - List files with filtering
    GET /api/library/languages - Get distinct audio languages
    GET /api/library/{file_id} - Get file detail
    GET /api/transcriptions - List transcriptions
    GET /api/transcriptions/{id} - Get transcription detail
"""

from __future__ import annotations

import asyncio
import logging

from aiohttp import web

from vpo.server.api.errors import INVALID_ID_FORMAT, NOT_FOUND, api_error
from vpo.server.middleware import (
    LIBRARY_ALLOWED_PARAMS,
    TRANSCRIPTIONS_ALLOWED_PARAMS,
    validate_query_params,
)
from vpo.server.ui.models import (
    FileDetailResponse,
    FileListItem,
    FileListResponse,
    LibraryFilterParams,
    TranscriptionDetailResponse,
    TranscriptionFilterParams,
    TranscriptionListItem,
    TranscriptionListResponse,
    build_file_detail_item,
    build_transcription_detail_item,
    format_audio_languages,
    format_detected_languages,
    get_confidence_level,
    get_resolution_label,
)
from vpo.server.ui.routes import (
    database_required_middleware,
    shutdown_check_middleware,
)

logger = logging.getLogger(__name__)


@shutdown_check_middleware
@database_required_middleware
@validate_query_params(LIBRARY_ALLOWED_PARAMS, strict=True)
async def library_api_handler(request: web.Request) -> web.Response:
    """Handle GET /api/library - JSON API for library files listing.

    Query parameters:
        status: Filter by scan status (ok, error)
        limit: Page size (1-100, default 50)
        offset: Pagination offset (default 0)

    Returns:
        JSON response with FileListResponse payload.
    """
    from vpo.db import get_files_filtered

    # Parse query parameters
    # Handle audio_lang as a list (can appear multiple times in query)
    query_dict = dict(request.query)
    if "audio_lang" in request.query:
        query_dict["audio_lang"] = request.query.getall("audio_lang")
    params = LibraryFilterParams.from_query(query_dict)

    # Log filter request for debugging (019-library-filters-search)
    active_filters = []
    if params.status:
        active_filters.append(f"status={params.status}")
    if params.search:
        active_filters.append(f"search={params.search!r}")
    if params.resolution:
        active_filters.append(f"resolution={params.resolution}")
    if params.audio_lang:
        active_filters.append(f"audio_lang={params.audio_lang}")
    if params.subtitles:
        active_filters.append(f"subtitles={params.subtitles}")
    if active_filters:
        logger.debug("Library API filter request: %s", ", ".join(active_filters))

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query files from database using thread-safe connection access
    def _query_files() -> tuple[list[dict], int]:
        with connection_pool.transaction() as conn:
            result = get_files_filtered(
                conn,
                status=params.status,
                search=params.search,
                resolution=params.resolution,
                audio_lang=params.audio_lang,
                subtitles=params.subtitles,
                limit=params.limit,
                offset=params.offset,
                return_total=True,
            )
            # Type narrowing: return_total=True always returns tuple
            return result  # type: ignore[return-value]

    files_data, total = await asyncio.to_thread(_query_files)

    # Transform to FileListItem
    files = [
        FileListItem(
            id=f["id"],
            filename=f["filename"],
            path=f["path"],
            title=f["video_title"],
            resolution=get_resolution_label(f["width"], f["height"]),
            audio_languages=format_audio_languages(f["audio_languages"]),
            scanned_at=f["scanned_at"],
            scan_status=f["scan_status"],
            scan_error=f["scan_error"],
        )
        for f in files_data
    ]

    # Determine if any filters are active (019-library-filters-search)
    has_filters = any(
        [
            params.status is not None,
            params.search is not None,
            params.resolution is not None,
            params.audio_lang is not None,
            params.subtitles is not None,
        ]
    )

    response = FileListResponse(
        files=files,
        total=total,
        limit=params.limit,
        offset=params.offset,
        has_filters=has_filters,
    )

    return web.json_response(response.to_dict())


@shutdown_check_middleware
@database_required_middleware
async def api_library_languages_handler(request: web.Request) -> web.Response:
    """Handle GET /api/library/languages - Get available audio languages.

    Returns list of distinct audio language codes present in the library
    for populating the language filter dropdown (019-library-filters-search).
    """
    from vpo.db import get_distinct_audio_languages

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query distinct languages from database
    def _query_languages() -> list[dict]:
        with connection_pool.transaction() as conn:
            return get_distinct_audio_languages(conn)

    languages = await asyncio.to_thread(_query_languages)

    return web.json_response({"languages": languages})


@shutdown_check_middleware
@database_required_middleware
async def api_file_detail_handler(request: web.Request) -> web.Response:
    """Handle GET /api/library/{file_id} - JSON API for file detail.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with FileDetailResponse payload or error.
    """
    from vpo.db import (
        get_file_by_id,
        get_tracks_for_file,
        get_transcriptions_for_tracks,
    )

    file_id_str = request.match_info["file_id"]

    # Validate ID format (integer)
    try:
        file_id = int(file_id_str)
        if file_id < 1:
            raise ValueError("Invalid ID")
    except ValueError:
        return api_error("Invalid file ID format", code=INVALID_ID_FORMAT)

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query file from database
    def _query_file():
        with connection_pool.transaction() as conn:
            file_record = get_file_by_id(conn, file_id)
            if file_record is None:
                return None, [], {}
            tracks = get_tracks_for_file(conn, file_record.id)
            # Get transcriptions for audio tracks
            audio_track_ids = [t.id for t in tracks if t.track_type == "audio"]
            transcriptions = get_transcriptions_for_tracks(conn, audio_track_ids)
            return file_record, tracks, transcriptions

    file_record, tracks, transcriptions = await asyncio.to_thread(_query_file)

    if file_record is None:
        return api_error("File not found", code=NOT_FOUND, status=404)

    # Build FileDetailItem
    detail_item = build_file_detail_item(file_record, tracks, transcriptions)

    # Build response
    response = FileDetailResponse(file=detail_item)

    return web.json_response(response.to_dict())


@shutdown_check_middleware
@database_required_middleware
@validate_query_params(TRANSCRIPTIONS_ALLOWED_PARAMS, strict=True)
async def api_transcriptions_handler(request: web.Request) -> web.Response:
    """Handle GET /api/transcriptions - JSON API for transcriptions listing.

    Query parameters:
        show_all: If true, show all files. Default: false (transcribed only).
        limit: Page size (1-100, default 50).
        offset: Pagination offset (default 0).

    Returns:
        JSON response with TranscriptionListResponse payload.
    """
    from vpo.db import get_files_with_transcriptions

    # Parse query parameters
    params = TranscriptionFilterParams.from_query(dict(request.query))

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query files from database using thread-safe connection access
    def _query_files() -> tuple[list[dict], int]:
        with connection_pool.transaction() as conn:
            result = get_files_with_transcriptions(
                conn,
                show_all=params.show_all,
                limit=params.limit,
                offset=params.offset,
                return_total=True,
            )
            # Type narrowing: return_total=True always returns tuple
            return result  # type: ignore[return-value]

    files_data, total = await asyncio.to_thread(_query_files)

    # Transform to TranscriptionListItem
    files = [
        TranscriptionListItem(
            id=f["id"],
            filename=f["filename"],
            path=f["path"],
            has_transcription=f["transcription_count"] > 0,
            detected_languages=format_detected_languages(f["detected_languages"]),
            confidence_level=get_confidence_level(f["avg_confidence"]),
            confidence_avg=f["avg_confidence"],
            transcription_count=f["transcription_count"],
            scan_status=f["scan_status"],
        )
        for f in files_data
    ]

    response = TranscriptionListResponse(
        files=files,
        total=total,
        limit=params.limit,
        offset=params.offset,
        has_filters=params.show_all,
    )

    return web.json_response(response.to_dict())


@shutdown_check_middleware
@database_required_middleware
async def api_transcription_detail_handler(request: web.Request) -> web.Response:
    """Handle GET /api/transcriptions/{id} - JSON API for transcription detail.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with TranscriptionDetailResponse payload or error.
    """
    from vpo.db import get_transcription_detail

    transcription_id_str = request.match_info["transcription_id"]

    # Validate ID format (integer)
    try:
        transcription_id = int(transcription_id_str)
        if transcription_id < 1:
            raise ValueError("Invalid ID")
    except ValueError:
        return api_error("Invalid transcription ID format", code=INVALID_ID_FORMAT)

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query transcription from database
    def _query_transcription():
        with connection_pool.transaction() as conn:
            return get_transcription_detail(conn, transcription_id)

    data = await asyncio.to_thread(_query_transcription)

    if data is None:
        return api_error("Transcription not found", code=NOT_FOUND, status=404)

    # Build detail item
    detail_item = build_transcription_detail_item(data)

    # Build response
    response = TranscriptionDetailResponse(transcription=detail_item)

    return web.json_response(response.to_dict())


def get_file_routes() -> list[tuple[str, str, object]]:
    """Return file/library API route definitions."""
    return [
        ("GET", "/library", library_api_handler),
        ("GET", "/library/languages", api_library_languages_handler),
        ("GET", "/library/{file_id}", api_file_detail_handler),
        ("GET", "/transcriptions", api_transcriptions_handler),
        ("GET", "/transcriptions/{transcription_id}", api_transcription_detail_handler),
    ]


def setup_file_routes(app: web.Application) -> None:
    """Register file/library API routes with the application.

    Args:
        app: aiohttp Application to configure.
    """
    for method, suffix, handler in get_file_routes():
        app.router.add_route(method, f"/api{suffix}", handler)
