"""Database migrations from schema version 21 to 25.

This module contains migrations for enhanced statistics features:
- v20→v21: Add encoder_type column for hardware encoder tracking (Issue #264)
"""

import sqlite3


def migrate_v20_to_v21(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 20 to version 21.

    Adds encoder_type column to processing_stats table for tracking whether
    hardware or software encoding was used (Issue #264):
    - encoder_type: 'hardware', 'software', or NULL if unknown

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check if column already exists (idempotent)
    cursor = conn.execute("PRAGMA table_info(processing_stats)")
    columns = {row[1] for row in cursor.fetchall()}
    if "encoder_type" not in columns:
        conn.execute("ALTER TABLE processing_stats ADD COLUMN encoder_type TEXT")

    # Update schema version to 21
    conn.execute(
        "UPDATE _meta SET value = '21' WHERE key = 'schema_version'",
    )
    conn.commit()
