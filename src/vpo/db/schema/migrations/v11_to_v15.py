"""Database migrations from schema version 11 to 15.

This module contains migrations for language analysis features:
- v10→v11: Language code normalization
- v11→v12: Plans table
- v12→v13: HDR color metadata columns
- v13→v14: Language analysis tables
- v14→v15: Track duration column
"""

import sqlite3


def migrate_v10_to_v11(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 10 to version 11.

    Normalizes all language codes to ISO 639-2/B standard:
    - tracks.language: Converts ISO 639-1 (2-letter) and ISO 639-2/T codes
      to ISO 639-2/B (3-letter bibliographic) codes
    - transcription_results.detected_language: Same normalization

    Examples of conversions:
    - "de" -> "ger" (ISO 639-1 to 639-2/B)
    - "deu" -> "ger" (ISO 639-2/T to 639-2/B)
    - "en" -> "eng"
    - "eng" -> "eng" (already 639-2/B, unchanged)

    This migration is idempotent - safe to run multiple times.
    Uses an exclusive transaction for atomicity - all changes succeed or
    all are rolled back on error.

    Args:
        conn: An open database connection.
    """
    import logging

    from vpo.language import normalize_language

    logger = logging.getLogger(__name__)

    # Start exclusive transaction for atomicity
    conn.execute("BEGIN EXCLUSIVE")
    try:
        # Normalize language codes in tracks table
        cursor = conn.execute(
            "SELECT DISTINCT language FROM tracks WHERE language IS NOT NULL"
        )
        track_languages = [row[0] for row in cursor.fetchall()]

        normalized_count = 0
        for lang in track_languages:
            normalized = normalize_language(lang, warn_on_conversion=False)
            if normalized != lang:
                # Skip unrecognized codes that would become "und"
                if normalized == "und" and lang.casefold().strip() not in ("", "und"):
                    logger.warning(
                        "Migration v10→v11: Skipping unrecognized language code '%s' "
                        "(would become 'und')",
                        lang,
                    )
                    continue

                conn.execute(
                    "UPDATE tracks SET language = ? WHERE language = ?",
                    (normalized, lang),
                )
                logger.info(
                    "Migration v10→v11: Normalized track language '%s' -> '%s'",
                    lang,
                    normalized,
                )
                normalized_count += 1

        # Normalize language codes in transcription_results table
        cursor = conn.execute(
            "SELECT DISTINCT detected_language FROM transcription_results "
            "WHERE detected_language IS NOT NULL"
        )
        transcription_languages = [row[0] for row in cursor.fetchall()]

        for lang in transcription_languages:
            normalized = normalize_language(lang, warn_on_conversion=False)
            if normalized != lang:
                # Skip unrecognized codes that would become "und"
                if normalized == "und" and lang.casefold().strip() not in ("", "und"):
                    logger.warning(
                        "Migration v10→v11: Skipping unrecognized language code '%s' "
                        "(would become 'und')",
                        lang,
                    )
                    continue

                conn.execute(
                    "UPDATE transcription_results SET detected_language = ? "
                    "WHERE detected_language = ?",
                    (normalized, lang),
                )
                logger.info(
                    "Migration v10→v11: Normalized transcription language '%s' -> '%s'",
                    lang,
                    normalized,
                )
                normalized_count += 1

        if normalized_count > 0:
            logger.info(
                "Migration v10→v11: Normalized %d distinct language codes",
                normalized_count,
            )

        # Update schema version to 11
        conn.execute(
            "UPDATE _meta SET value = '11' WHERE key = 'schema_version'",
        )

        # Commit transaction
        conn.execute("COMMIT")

    except Exception as e:
        # Rollback on any error
        conn.execute("ROLLBACK")
        logger.error("Migration v10→v11 failed, rolling back: %s", e)
        raise


def migrate_v11_to_v12(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 11 to version 12.

    Adds plans table for the approval workflow (026-plans-list-view):
    - Stores planned changes awaiting operator approval
    - Tracks status through pending → approved/rejected → applied/canceled
    - Foreign key to files with ON DELETE SET NULL for deleted file handling
    - Indexes for common queries: status, created_at, file_id, policy_name

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check if table already exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='plans'"
    )
    if cursor.fetchone() is None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS plans (
                id TEXT PRIMARY KEY,
                file_id INTEGER,
                file_path TEXT NOT NULL,
                policy_name TEXT NOT NULL,
                policy_version INTEGER NOT NULL,
                job_id TEXT,
                actions_json TEXT NOT NULL,
                action_count INTEGER NOT NULL,
                requires_remux INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE SET NULL,
                CONSTRAINT valid_status CHECK (
                    status IN ('pending', 'approved', 'rejected', 'applied', 'canceled')
                ),
                CONSTRAINT valid_action_count CHECK (action_count >= 0)
            );

            CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(status);
            CREATE INDEX IF NOT EXISTS idx_plans_created_at ON plans(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_plans_file_id ON plans(file_id);
            CREATE INDEX IF NOT EXISTS idx_plans_policy_name ON plans(policy_name);
        """)

    # Update schema version to 12
    conn.execute(
        "UPDATE _meta SET value = '12' WHERE key = 'schema_version'",
    )
    conn.commit()


def migrate_v12_to_v13(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 12 to version 13.

    Adds HDR color metadata columns to the tracks table for the
    conditional video transcode feature (034-conditional-video-transcode):
    - color_transfer: Transfer characteristics (e.g., smpte2084, arib-std-b67)
    - color_primaries: Color primaries (e.g., bt2020)
    - color_space: Color space (e.g., bt2020nc)
    - color_range: Color range (e.g., tv, pc)

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check if columns already exist by looking at table info
    cursor = conn.execute("PRAGMA table_info(tracks)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # Add each HDR color metadata column if it doesn't exist
    # Using explicit statements instead of dynamic SQL for clarity
    if "color_transfer" not in existing_columns:
        conn.execute("ALTER TABLE tracks ADD COLUMN color_transfer TEXT")
    if "color_primaries" not in existing_columns:
        conn.execute("ALTER TABLE tracks ADD COLUMN color_primaries TEXT")
    if "color_space" not in existing_columns:
        conn.execute("ALTER TABLE tracks ADD COLUMN color_space TEXT")
    if "color_range" not in existing_columns:
        conn.execute("ALTER TABLE tracks ADD COLUMN color_range TEXT")

    # Update schema version to 13
    conn.execute(
        "UPDATE _meta SET value = '13' WHERE key = 'schema_version'",
    )
    conn.commit()


def migrate_v13_to_v14(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 13 to version 14.

    Adds language analysis tables for multi-language audio detection
    (035-multi-language-audio-detection):
    - language_analysis_results: Stores aggregated language analysis per track
    - language_segments: Stores individual language detections within tracks

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check if language_analysis_results table already exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name='language_analysis_results'"
    )
    if cursor.fetchone() is None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS language_analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL UNIQUE,
                file_hash TEXT NOT NULL,
                primary_language TEXT NOT NULL,
                primary_percentage REAL NOT NULL,
                classification TEXT NOT NULL,
                analysis_metadata TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
                CONSTRAINT valid_percentage CHECK (
                    primary_percentage >= 0.0 AND primary_percentage <= 1.0
                ),
                CONSTRAINT valid_classification CHECK (
                    classification IN ('SINGLE_LANGUAGE', 'MULTI_LANGUAGE')
                )
            );

            CREATE INDEX IF NOT EXISTS idx_lang_analysis_track
                ON language_analysis_results(track_id);
            CREATE INDEX IF NOT EXISTS idx_lang_analysis_hash
                ON language_analysis_results(file_hash);
            CREATE INDEX IF NOT EXISTS idx_lang_analysis_classification
                ON language_analysis_results(classification);
        """)

    # Check if language_segments table already exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='language_segments'"
    )
    if cursor.fetchone() is None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS language_segments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                language_code TEXT NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                confidence REAL NOT NULL,
                FOREIGN KEY (analysis_id)
                    REFERENCES language_analysis_results(id) ON DELETE CASCADE,
                CONSTRAINT valid_times CHECK (end_time > start_time),
                CONSTRAINT valid_confidence CHECK (
                    confidence >= 0.0 AND confidence <= 1.0
                )
            );

            CREATE INDEX IF NOT EXISTS idx_lang_segments_analysis
                ON language_segments(analysis_id);
            CREATE INDEX IF NOT EXISTS idx_lang_segments_language
                ON language_segments(language_code);
        """)

    # Update schema version to 14
    conn.execute(
        "UPDATE _meta SET value = '14' WHERE key = 'schema_version'",
    )
    conn.commit()


def migrate_v14_to_v15(conn: sqlite3.Connection) -> None:
    """Migrate database from schema version 14 to version 15.

    Adds duration_seconds column to tracks table for accurate track duration
    storage (035-multi-language-audio-detection).

    This migration is idempotent - safe to run multiple times.

    Args:
        conn: An open database connection.
    """
    # Check if column already exists (idempotent)
    cursor = conn.execute("PRAGMA table_info(tracks)")
    columns = {row[1] for row in cursor.fetchall()}
    if "duration_seconds" not in columns:
        conn.execute("ALTER TABLE tracks ADD COLUMN duration_seconds REAL")

    # Update schema version to 15
    conn.execute(
        "UPDATE _meta SET value = '15' WHERE key = 'schema_version'",
    )
    conn.commit()
