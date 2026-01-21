"""Plugin data view query functions."""

import re
import sqlite3

from vpo.core.json_utils import parse_json_safe

from .helpers import _clamp_limit


def get_files_with_plugin_data(
    conn: sqlite3.Connection,
    plugin_name: str,
    *,
    limit: int | None = None,
    offset: int | None = None,
    return_total: bool = False,
) -> list[dict] | tuple[list[dict], int]:
    """Get files that have data from a specific plugin.

    Queries files where plugin_metadata JSON contains data for the
    specified plugin name.

    Args:
        conn: Database connection.
        plugin_name: Plugin identifier to filter by (e.g., "whisper-transcriber").
        limit: Maximum files to return.
        offset: Pagination offset.
        return_total: If True, return tuple of (files, total_count).

    Returns:
        List of file dicts with plugin data:
        {
            "id": int,
            "filename": str,
            "path": str,
            "scan_status": str,
            "plugin_data": dict,  # Parsed plugin-specific data
        }

    Raises:
        ValueError: If plugin_name contains invalid characters.
    """
    # Validate plugin name for defense in depth (routes also validate)
    if not re.match(r"^[a-zA-Z0-9_-]+$", plugin_name):
        raise ValueError(f"Invalid plugin name format: {plugin_name}")

    # Enforce pagination limits to prevent memory exhaustion
    limit = _clamp_limit(limit)

    # Build query - use window function for total count when needed
    # This avoids a separate COUNT query (single query optimization)
    if return_total:
        query = """
            SELECT
                id, filename, path, scan_status, plugin_metadata,
                COUNT(*) OVER() as total_count
            FROM files
            WHERE plugin_metadata IS NOT NULL
            AND json_extract(plugin_metadata, ?) IS NOT NULL
            ORDER BY filename
        """
    else:
        query = """
            SELECT
                id, filename, path, scan_status, plugin_metadata
            FROM files
            WHERE plugin_metadata IS NOT NULL
            AND json_extract(plugin_metadata, ?) IS NOT NULL
            ORDER BY filename
        """

    # Add pagination
    params: list[str | int] = [f"$.{plugin_name}"]
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
        if offset is not None:
            query += " OFFSET ?"
            params.append(offset)

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    # Extract total from first row if using window function (or 0 if empty)
    total = rows[0][5] if return_total and rows else 0

    files = []
    for row in rows:
        result = parse_json_safe(row[4], default={}, context="plugin_metadata")
        plugin_metadata = result.value or {}
        files.append(
            {
                "id": row[0],
                "filename": row[1],
                "path": row[2],
                "scan_status": row[3],
                "plugin_data": plugin_metadata.get(plugin_name, {}),
            }
        )

    if return_total:
        return files, total
    return files


def get_plugin_data_for_file(
    conn: sqlite3.Connection,
    file_id: int,
) -> dict[str, dict]:
    """Get all plugin metadata for a specific file.

    Args:
        conn: Database connection.
        file_id: ID of file to look up.

    Returns:
        Dictionary keyed by plugin name with each plugin's data.
        Empty dict if file not found, no plugin metadata, or malformed JSON.
    """
    cursor = conn.execute(
        "SELECT plugin_metadata FROM files WHERE id = ?",
        (file_id,),
    )
    row = cursor.fetchone()

    if row is None or row[0] is None:
        return {}

    result = parse_json_safe(
        row[0], default={}, context=f"plugin_metadata for file_id={file_id}"
    )
    return result.value or {}
