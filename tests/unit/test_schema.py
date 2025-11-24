"""Unit tests for database schema."""

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest


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
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
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


class TestMigrationV10ToV11:
    """Tests for v10 to v11 migration (language normalization)."""

    @pytest.fixture
    def db_v10(self, tmp_path: Path) -> sqlite3.Connection:
        """Create a database at version 10 with test data."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        # Create minimal schema for testing
        conn.executescript(
            """
            CREATE TABLE _meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            INSERT INTO _meta (key, value) VALUES ('schema_version', '10');

            CREATE TABLE files (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE NOT NULL
            );
            INSERT INTO files (id, path) VALUES
                (1, '/test1.mkv'),
                (2, '/test2.mkv');

            CREATE TABLE tracks (
                id INTEGER PRIMARY KEY,
                file_id INTEGER NOT NULL,
                language TEXT,
                FOREIGN KEY (file_id) REFERENCES files(id)
            );
            INSERT INTO tracks (id, file_id, language) VALUES
                (1, 1, 'de'),      -- German ISO 639-1
                (2, 1, 'deu'),     -- German ISO 639-2/T
                (3, 1, 'ger'),     -- German ISO 639-2/B (already correct)
                (4, 1, 'en'),      -- English ISO 639-1
                (5, 2, 'fra'),     -- French ISO 639-2/T
                (6, 2, NULL);      -- NULL should remain NULL

            CREATE TABLE transcription_results (
                id INTEGER PRIMARY KEY,
                track_id INTEGER NOT NULL,
                detected_language TEXT,
                FOREIGN KEY (track_id) REFERENCES tracks(id)
            );
            INSERT INTO transcription_results (id, track_id, detected_language) VALUES
                (1, 1, 'de'),      -- German ISO 639-1
                (2, 2, 'zho'),     -- Chinese ISO 639-2/T
                (3, 3, 'chi');     -- Chinese ISO 639-2/B (already correct)
            """
        )

        conn.commit()
        return conn

    def test_migration_normalizes_languages(self, db_v10: sqlite3.Connection):
        """Test that migration correctly normalizes language codes."""
        from video_policy_orchestrator.db.schema import migrate_v10_to_v11

        # Run migration
        migrate_v10_to_v11(db_v10)

        # Check tracks table
        cursor = db_v10.execute("SELECT id, language FROM tracks ORDER BY id")
        tracks = cursor.fetchall()

        assert tracks[0][1] == "ger"  # de -> ger
        assert tracks[1][1] == "ger"  # deu -> ger
        assert tracks[2][1] == "ger"  # ger -> ger (unchanged)
        assert tracks[3][1] == "eng"  # en -> eng
        assert tracks[4][1] == "fre"  # fra -> fre
        assert tracks[5][1] is None  # NULL -> NULL

        # Check transcription_results table
        cursor = db_v10.execute(
            "SELECT id, detected_language FROM transcription_results ORDER BY id"
        )
        results = cursor.fetchall()

        assert results[0][1] == "ger"  # de -> ger
        assert results[1][1] == "chi"  # zho -> chi
        assert results[2][1] == "chi"  # chi -> chi (unchanged)

        # Check schema version updated
        cursor = db_v10.execute("SELECT value FROM _meta WHERE key = 'schema_version'")
        assert cursor.fetchone()[0] == "11"

    def test_migration_is_idempotent(self, db_v10: sqlite3.Connection):
        """Test that running migration twice doesn't error."""
        from video_policy_orchestrator.db.schema import migrate_v10_to_v11

        # Run migration twice
        migrate_v10_to_v11(db_v10)
        migrate_v10_to_v11(db_v10)

        # Verify data is still correct
        cursor = db_v10.execute("SELECT language FROM tracks WHERE id = 1")
        assert cursor.fetchone()[0] == "ger"

    def test_migration_preserves_null_values(self, db_v10: sqlite3.Connection):
        """Test that NULL languages remain NULL."""
        from video_policy_orchestrator.db.schema import migrate_v10_to_v11

        # Run migration
        migrate_v10_to_v11(db_v10)

        # Check NULL was preserved
        cursor = db_v10.execute("SELECT language FROM tracks WHERE id = 6")
        assert cursor.fetchone()[0] is None

    def test_migration_skips_unknown_codes(self, tmp_path: Path):
        """Test that migration skips unrecognized language codes."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        # Create database with unknown language code
        conn.executescript(
            """
            CREATE TABLE _meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO _meta (key, value) VALUES ('schema_version', '10');
            CREATE TABLE files (id INTEGER PRIMARY KEY, path TEXT);
            INSERT INTO files (id, path) VALUES (1, '/test.mkv');
            CREATE TABLE tracks (
                id INTEGER PRIMARY KEY, file_id INTEGER, language TEXT
            );
            INSERT INTO tracks (id, file_id, language) VALUES (1, 1, 'xxx');
            CREATE TABLE transcription_results (
                id INTEGER PRIMARY KEY, track_id INTEGER, detected_language TEXT
            );
            """
        )
        conn.commit()

        from video_policy_orchestrator.db.schema import migrate_v10_to_v11

        # Run migration - should handle unknown code gracefully
        migrate_v10_to_v11(conn)

        # Check that unknown code was preserved (not converted to "und")
        cursor = conn.execute("SELECT language FROM tracks WHERE id = 1")
        result = cursor.fetchone()[0]
        assert result == "xxx"  # Should be preserved

        conn.close()

    def test_migration_rollback_on_error(self, tmp_path: Path):
        """Test that migration rolls back on error."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        # Create database with multiple distinct languages to trigger multiple
        # normalize_language calls
        conn.executescript(
            """
            CREATE TABLE _meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO _meta (key, value) VALUES ('schema_version', '10');
            CREATE TABLE files (id INTEGER PRIMARY KEY, path TEXT);
            INSERT INTO files (id, path) VALUES (1, '/test.mkv');
            CREATE TABLE tracks (
                id INTEGER PRIMARY KEY, file_id INTEGER, language TEXT
            );
            INSERT INTO tracks (id, file_id, language) VALUES
                (1, 1, 'de'),
                (2, 1, 'fr'),
                (3, 1, 'es');
            CREATE TABLE transcription_results (
                id INTEGER PRIMARY KEY, track_id INTEGER, detected_language TEXT
            );
            """
        )
        conn.commit()

        from video_policy_orchestrator.db.schema import migrate_v10_to_v11

        # Mock normalize_language to raise an error after processing first language
        # Patch at the source module since it's imported inside the function
        call_count = 0

        def mock_normalize(code, warn_on_conversion=True):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise RuntimeError("Simulated error during migration")
            return "ger"  # Return normalized value for first call

        with patch(
            "video_policy_orchestrator.language.normalize_language", mock_normalize
        ):
            with pytest.raises(RuntimeError, match="Simulated error"):
                migrate_v10_to_v11(conn)

        # Verify rollback: schema version should still be 10
        cursor = conn.execute("SELECT value FROM _meta WHERE key = 'schema_version'")
        assert cursor.fetchone()[0] == "10"

        # Verify rollback: first language should be unchanged (rollback undid UPDATE)
        cursor = conn.execute("SELECT language FROM tracks WHERE id = 1")
        assert cursor.fetchone()[0] == "de"

        conn.close()
