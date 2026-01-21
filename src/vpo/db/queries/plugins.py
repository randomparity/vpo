"""Plugin acknowledgment CRUD operations for Video Policy Orchestrator database.

This module contains database query functions for plugin acknowledgments:
- Plugin acknowledgment insert, get, check, delete operations
"""

import sqlite3

from vpo.db.types import PluginAcknowledgment


def get_plugin_acknowledgment(
    conn: sqlite3.Connection, plugin_name: str, plugin_hash: str
) -> PluginAcknowledgment | None:
    """Get a plugin acknowledgment by name and hash.

    Args:
        conn: Database connection.
        plugin_name: Plugin identifier.
        plugin_hash: SHA-256 hash of plugin file(s).

    Returns:
        PluginAcknowledgment if found, None otherwise.
    """
    cursor = conn.execute(
        """
        SELECT id, plugin_name, plugin_hash, acknowledged_at, acknowledged_by
        FROM plugin_acknowledgments
        WHERE plugin_name = ? AND plugin_hash = ?
        """,
        (plugin_name, plugin_hash),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    return PluginAcknowledgment(
        id=row[0],
        plugin_name=row[1],
        plugin_hash=row[2],
        acknowledged_at=row[3],
        acknowledged_by=row[4],
    )


def is_plugin_acknowledged(
    conn: sqlite3.Connection, plugin_name: str, plugin_hash: str
) -> bool:
    """Check if a plugin has been acknowledged with the given hash.

    Args:
        conn: Database connection.
        plugin_name: Plugin identifier.
        plugin_hash: SHA-256 hash of plugin file(s).

    Returns:
        True if acknowledged, False otherwise.
    """
    return get_plugin_acknowledgment(conn, plugin_name, plugin_hash) is not None


def insert_plugin_acknowledgment(
    conn: sqlite3.Connection, record: PluginAcknowledgment
) -> int:
    """Insert a new plugin acknowledgment record.

    Args:
        conn: Database connection.
        record: PluginAcknowledgment to insert.

    Returns:
        The ID of the inserted record.

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    cursor = conn.execute(
        """
        INSERT INTO plugin_acknowledgments (
            plugin_name, plugin_hash, acknowledged_at, acknowledged_by
        ) VALUES (?, ?, ?, ?)
        """,
        (
            record.plugin_name,
            record.plugin_hash,
            record.acknowledged_at,
            record.acknowledged_by,
        ),
    )
    return cursor.lastrowid


def get_acknowledgments_for_plugin(
    conn: sqlite3.Connection, plugin_name: str
) -> list[PluginAcknowledgment]:
    """Get all acknowledgments for a plugin (all hash versions).

    Args:
        conn: Database connection.
        plugin_name: Plugin identifier.

    Returns:
        List of PluginAcknowledgment records.
    """
    cursor = conn.execute(
        """
        SELECT id, plugin_name, plugin_hash, acknowledged_at, acknowledged_by
        FROM plugin_acknowledgments
        WHERE plugin_name = ?
        ORDER BY acknowledged_at DESC
        """,
        (plugin_name,),
    )
    return [
        PluginAcknowledgment(
            id=row[0],
            plugin_name=row[1],
            plugin_hash=row[2],
            acknowledged_at=row[3],
            acknowledged_by=row[4],
        )
        for row in cursor.fetchall()
    ]


def delete_plugin_acknowledgment(
    conn: sqlite3.Connection, plugin_name: str, plugin_hash: str
) -> bool:
    """Delete a plugin acknowledgment.

    Args:
        conn: Database connection.
        plugin_name: Plugin identifier.
        plugin_hash: SHA-256 hash of plugin file(s).

    Returns:
        True if a record was deleted, False otherwise.

    Note:
        This function does NOT commit. Caller must manage transactions.
    """
    cursor = conn.execute(
        """
        DELETE FROM plugin_acknowledgments
        WHERE plugin_name = ? AND plugin_hash = ?
        """,
        (plugin_name, plugin_hash),
    )
    return cursor.rowcount > 0
