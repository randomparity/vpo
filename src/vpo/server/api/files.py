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

from vpo.core.json_utils import parse_json_safe
from vpo.server.middleware import TRANSCRIPTIONS_ALLOWED_PARAMS, validate_query_params
from vpo.server.ui.models import (
    FileDetailItem,
    FileDetailResponse,
    FileListItem,
    FileListResponse,
    LibraryFilterParams,
    TranscriptionDetailItem,
    TranscriptionDetailResponse,
    TranscriptionFilterParams,
    TranscriptionListItem,
    TranscriptionListResponse,
    format_audio_languages,
    format_detected_languages,
    format_file_size,
    get_classification_reasoning,
    get_confidence_level,
    get_resolution_label,
    group_tracks_by_type,
    highlight_keywords_in_transcript,
)
from vpo.server.ui.routes import (
    database_required_middleware,
    shutdown_check_middleware,
)

logger = logging.getLogger(__name__)


def _build_file_detail_item(file_record, tracks, transcriptions) -> FileDetailItem:
    """Build FileDetailItem from database records.

    Args:
        file_record: FileRecord from database.
        tracks: List of TrackRecord from database.
        transcriptions: Dict mapping track_id to TranscriptionResultRecord.

    Returns:
        FileDetailItem ready for API/template use.
    """

    # Group tracks by type
    video_tracks, audio_tracks, subtitle_tracks, other_tracks = group_tracks_by_type(
        tracks, transcriptions
    )

    # Parse plugin_metadata JSON (236-generic-plugin-data-browser)
    plugin_result = parse_json_safe(
        file_record.plugin_metadata,
        context=f"plugin_metadata for file {file_record.id}",
    )
    plugin_metadata = plugin_result.value

    return FileDetailItem(
        id=file_record.id,
        path=file_record.path,
        filename=file_record.filename,
        directory=file_record.directory,
        extension=file_record.extension,
        container_format=file_record.container_format,
        size_bytes=file_record.size_bytes,
        size_human=format_file_size(file_record.size_bytes),
        modified_at=file_record.modified_at,
        scanned_at=file_record.scanned_at,
        scan_status=file_record.scan_status,
        scan_error=file_record.scan_error,
        scan_job_id=file_record.job_id,
        video_tracks=video_tracks,
        audio_tracks=audio_tracks,
        subtitle_tracks=subtitle_tracks,
        other_tracks=other_tracks,
        plugin_metadata=plugin_metadata,
    )


def _build_transcription_detail_item(data: dict) -> TranscriptionDetailItem:
    """Build TranscriptionDetailItem from database query result.

    Args:
        data: Dictionary from get_transcription_detail() query.

    Returns:
        TranscriptionDetailItem ready for API/template use.
    """
    track_type = data["track_type"]
    transcript = data["transcript_sample"]

    # Get classification reasoning
    classification_source, matched_keywords = get_classification_reasoning(
        data["title"],
        transcript,
        track_type,
    )

    # Generate highlighted HTML
    transcript_html, transcript_truncated = highlight_keywords_in_transcript(
        transcript,
        track_type,
    )

    return TranscriptionDetailItem(
        id=data["id"],
        track_id=data["track_id"],
        detected_language=data["detected_language"],
        confidence_score=data["confidence_score"],
        confidence_level=get_confidence_level(data["confidence_score"]),
        track_classification=track_type,
        transcript_sample=transcript,
        transcript_html=transcript_html,
        transcript_truncated=transcript_truncated,
        plugin_name=data["plugin_name"],
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        track_index=data["track_index"],
        track_codec=data["codec"],
        original_language=data["original_language"],
        track_title=data["title"],
        channels=data["channels"],
        channel_layout=data["channel_layout"],
        is_default=bool(data["is_default"]),
        is_forced=bool(data["is_forced"]),
        is_commentary=track_type == "commentary",
        classification_source=classification_source,
        matched_keywords=matched_keywords,
        file_id=data["file_id"],
        filename=data["filename"],
        file_path=data["path"],
    )


@shutdown_check_middleware
@database_required_middleware
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
        return web.json_response(
            {"error": "Invalid file ID format"},
            status=400,
        )

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
        return web.json_response(
            {"error": "File not found"},
            status=404,
        )

    # Build FileDetailItem
    detail_item = _build_file_detail_item(file_record, tracks, transcriptions)

    # Build response
    response = FileDetailResponse(file=detail_item)

    return web.json_response(response.to_dict())


@shutdown_check_middleware
@database_required_middleware
@validate_query_params(TRANSCRIPTIONS_ALLOWED_PARAMS)
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
        return web.json_response(
            {"error": "Invalid transcription ID format"},
            status=400,
        )

    # Get connection pool from middleware
    connection_pool = request["connection_pool"]

    # Query transcription from database
    def _query_transcription():
        with connection_pool.transaction() as conn:
            return get_transcription_detail(conn, transcription_id)

    data = await asyncio.to_thread(_query_transcription)

    if data is None:
        return web.json_response(
            {"error": "Transcription not found"},
            status=404,
        )

    # Build detail item
    detail_item = _build_transcription_detail_item(data)

    # Build response
    response = TranscriptionDetailResponse(transcription=detail_item)

    return web.json_response(response.to_dict())


def setup_file_routes(app: web.Application) -> None:
    """Register file/library API routes with the application.

    Args:
        app: aiohttp Application to configure.
    """
    # Library API routes (018-library-list-view, 019-library-filters-search)
    app.router.add_get("/api/library", library_api_handler)
    app.router.add_get("/api/library/languages", api_library_languages_handler)
    # File detail route (020-file-detail-view)
    app.router.add_get("/api/library/{file_id}", api_file_detail_handler)
    # Transcription routes
    app.router.add_get("/api/transcriptions", api_transcriptions_handler)
    app.router.add_get(
        "/api/transcriptions/{transcription_id}", api_transcription_detail_handler
    )
