"""Unit tests for database schema."""

import sqlite3
from pathlib import Path


class TestSchemaCreation:
    """Tests for schema creation and initialization."""

    def test_create_schema_creates_tables(self, temp_db: Path):
        """Test that create_schema creates all required tables."""
        from video_policy_orchestrator.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        create_schema(conn)

        # Check all tables exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}

        assert "_meta" in tables
        assert "files" in tables
        assert "tracks" in tables
        assert "operations" in tables
        assert "policies" in tables

        conn.close()

    def test_create_schema_sets_version(self, temp_db: Path):
        """Test that schema version is set correctly."""
        from video_policy_orchestrator.db.schema import (
            SCHEMA_VERSION,
            create_schema,
            get_schema_version,
        )

        conn = sqlite3.connect(str(temp_db))
        create_schema(conn)

        version = get_schema_version(conn)
        assert version == SCHEMA_VERSION

        conn.close()

    def test_create_schema_is_idempotent(self, temp_db: Path):
        """Test that calling create_schema twice doesn't error."""
        from video_policy_orchestrator.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        create_schema(conn)
        create_schema(conn)  # Should not raise

        conn.close()

    def test_initialize_database(self, temp_db: Path):
        """Test database initialization."""
        from video_policy_orchestrator.db.schema import initialize_database

        conn = sqlite3.connect(str(temp_db))
        initialize_database(conn)

        # Verify tables exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        assert "files" in tables

        conn.close()

    def test_files_table_has_correct_columns(self, temp_db: Path):
        """Test that files table has all required columns."""
        from video_policy_orchestrator.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        create_schema(conn)

        cursor = conn.execute("PRAGMA table_info(files)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            "id",
            "path",
            "filename",
            "directory",
            "extension",
            "size_bytes",
            "modified_at",
            "content_hash",
            "container_format",
            "scanned_at",
            "scan_status",
            "scan_error",
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_tracks_table_has_correct_columns(self, temp_db: Path):
        """Test that tracks table has all required columns."""
        from video_policy_orchestrator.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        create_schema(conn)

        cursor = conn.execute("PRAGMA table_info(tracks)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            "id",
            "file_id",
            "track_index",
            "track_type",
            "codec",
            "language",
            "title",
            "is_default",
            "is_forced",
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_foreign_key_constraint(self, temp_db: Path):
        """Test that foreign key constraints are enforced."""
        from video_policy_orchestrator.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.execute("PRAGMA foreign_keys = ON")
        create_schema(conn)

        # Try to insert a track with non-existent file_id
        import pytest

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO tracks (file_id, track_index, track_type)
                VALUES (999, 0, 'video')
                """
            )

        conn.close()
