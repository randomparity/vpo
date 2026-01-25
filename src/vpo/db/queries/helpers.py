"""Shared helper functions for database queries.

This module provides utility functions used across multiple query modules:
- SQL pattern escaping for LIKE queries
- Row mapping functions to convert database rows to typed dataclasses
"""

import sqlite3

from vpo.db.types import (
    FileRecord,
    Job,
    JobStatus,
    JobType,
    TrackRecord,
)


def _escape_like_pattern(value: str) -> str:
    """Escape special characters in SQL LIKE patterns.

    SQLite LIKE patterns treat %, _, and [ as special characters.
    This function escapes them so they match literally.

    Args:
        value: The string to escape for use in a LIKE pattern.

    Returns:
        Escaped string safe for LIKE pattern matching.

    Note:
        Queries using this must include ESCAPE '\\' clause.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _row_to_file_record(row: sqlite3.Row) -> FileRecord:
    """Convert a database row to FileRecord using named columns.

    Args:
        row: sqlite3.Row from a SELECT query on the files table.

    Returns:
        FileRecord instance populated from the row.
    """
    return FileRecord(
        id=row["id"],
        path=row["path"],
        filename=row["filename"],
        directory=row["directory"],
        extension=row["extension"],
        size_bytes=row["size_bytes"],
        modified_at=row["modified_at"],
        content_hash=row["content_hash"],
        container_format=row["container_format"],
        scanned_at=row["scanned_at"],
        scan_status=row["scan_status"],
        scan_error=row["scan_error"],
        job_id=row["job_id"],
        plugin_metadata=row["plugin_metadata"],
    )


def _row_to_track_record(row: sqlite3.Row) -> TrackRecord:
    """Convert a database row to TrackRecord using named columns.

    Args:
        row: sqlite3.Row from a SELECT query on the tracks table.

    Returns:
        TrackRecord instance populated from the row.
    """
    return TrackRecord(
        id=row["id"],
        file_id=row["file_id"],
        track_index=row["track_index"],
        track_type=row["track_type"],
        codec=row["codec"],
        language=row["language"],
        title=row["title"],
        is_default=row["is_default"] == 1,
        is_forced=row["is_forced"] == 1,
        channels=row["channels"],
        channel_layout=row["channel_layout"],
        width=row["width"],
        height=row["height"],
        frame_rate=row["frame_rate"],
        color_transfer=row["color_transfer"],
        color_primaries=row["color_primaries"],
        color_space=row["color_space"],
        color_range=row["color_range"],
        duration_seconds=row["duration_seconds"],
    )


def _row_to_job(row: sqlite3.Row) -> Job:
    """Convert a database row to a Job object.

    Args:
        row: sqlite3.Row from a SELECT query on the jobs table.

    Returns:
        Job instance populated from the row.
    """
    # Handle optional columns that may not exist in older databases
    # before migration v22→v23 is applied
    origin = row["origin"] if "origin" in row.keys() else None
    batch_id = row["batch_id"] if "batch_id" in row.keys() else None

    return Job(
        id=row["id"],
        file_id=row["file_id"],
        file_path=row["file_path"],
        job_type=JobType(row["job_type"]),
        status=JobStatus(row["status"]),
        priority=row["priority"],
        policy_name=row["policy_name"],
        policy_json=row["policy_json"],
        progress_percent=row["progress_percent"],
        progress_json=row["progress_json"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        worker_pid=row["worker_pid"],
        worker_heartbeat=row["worker_heartbeat"],
        output_path=row["output_path"],
        backup_path=row["backup_path"],
        error_message=row["error_message"],
        files_affected_json=row["files_affected_json"],
        summary_json=row["summary_json"],
        log_path=row["log_path"],
        origin=origin,
        batch_id=batch_id,
    )
