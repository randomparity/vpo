"""Unit tests for database schema."""

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest


class TestSchemaCreation:
    """Tests for schema creation and initialization."""

    def test_create_schema_creates_tables(self, temp_db: Path):
        """Test that create_schema creates all required tables."""
        from vpo.db.schema import create_schema

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
        from vpo.db.schema import (
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
        from vpo.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        create_schema(conn)
        create_schema(conn)  # Should not raise

        conn.close()

    def test_initialize_database(self, temp_db: Path):
        """Test database initialization."""
        from vpo.db.schema import initialize_database

        conn = sqlite3.connect(str(temp_db))
        initialize_database(conn)

        # Verify tables exist
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        assert "files" in tables

        conn.close()

    def test_files_table_has_correct_columns(self, temp_db: Path):
        """Test that files table has all required columns."""
        from vpo.db.schema import create_schema

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
        from vpo.db.schema import create_schema

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
        from vpo.db.schema import create_schema

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
        from vpo.db.schema import migrate_v10_to_v11

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
        from vpo.db.schema import migrate_v10_to_v11

        # Run migration twice
        migrate_v10_to_v11(db_v10)
        migrate_v10_to_v11(db_v10)

        # Verify data is still correct
        cursor = db_v10.execute("SELECT language FROM tracks WHERE id = 1")
        assert cursor.fetchone()[0] == "ger"

    def test_migration_preserves_null_values(self, db_v10: sqlite3.Connection):
        """Test that NULL languages remain NULL."""
        from vpo.db.schema import migrate_v10_to_v11

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

        from vpo.db.schema import migrate_v10_to_v11

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

        from vpo.db.schema import migrate_v10_to_v11

        # Mock normalize_language to raise an error after processing first language
        # Patch at the source module since it's imported inside the function
        call_count = 0

        def mock_normalize(code, warn_on_conversion=True):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise RuntimeError("Simulated error during migration")
            return "ger"  # Return normalized value for first call

        with patch("vpo.language.normalize_language", mock_normalize):
            with pytest.raises(RuntimeError, match="Simulated error"):
                migrate_v10_to_v11(conn)

        # Verify rollback: schema version should still be 10
        cursor = conn.execute("SELECT value FROM _meta WHERE key = 'schema_version'")
        assert cursor.fetchone()[0] == "10"

        # Verify rollback: first language should be unchanged (rollback undid UPDATE)
        cursor = conn.execute("SELECT language FROM tracks WHERE id = 1")
        assert cursor.fetchone()[0] == "de"

        conn.close()


class TestMigrationV15ToV16:
    """Tests for v15 to v16 migration (expanded track_type constraint)."""

    @pytest.fixture
    def db_v15(self, tmp_path: Path) -> sqlite3.Connection:
        """Create a database at version 15 with test data."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        # Create minimal schema at v15 with old CHECK constraint
        conn.executescript(
            """
            CREATE TABLE _meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            INSERT INTO _meta (key, value) VALUES ('schema_version', '15');

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
                track_type TEXT,
                language TEXT,
                FOREIGN KEY (file_id) REFERENCES files(id)
            );
            INSERT INTO tracks (id, file_id, track_type, language) VALUES
                (1, 1, 'audio', 'eng'),
                (2, 1, 'audio', 'fre'),
                (3, 2, 'audio', 'eng');

            CREATE TABLE transcription_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL UNIQUE,
                detected_language TEXT,
                confidence_score REAL NOT NULL,
                track_type TEXT NOT NULL DEFAULT 'main',
                transcript_sample TEXT,
                plugin_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
                CONSTRAINT valid_confidence CHECK (
                    confidence_score >= 0.0 AND confidence_score <= 1.0
                ),
                CONSTRAINT valid_track_type CHECK (
                    track_type IN ('main', 'commentary', 'alternate')
                )
            );
            INSERT INTO transcription_results (
                track_id, detected_language, confidence_score, track_type,
                transcript_sample, plugin_name, created_at, updated_at
            ) VALUES
                (1, 'eng', 0.95, 'main', 'Hello world...', 'whisper-local',
                 '2025-01-15T10:00:00+00:00', '2025-01-15T10:00:00+00:00'),
                (2, 'fre', 0.85, 'commentary', 'Bonjour...', 'whisper-local',
                 '2025-01-15T10:05:00+00:00', '2025-01-15T10:05:00+00:00'),
                (3, 'eng', 0.90, 'alternate', 'Alt track...', 'whisper-local',
                 '2025-01-15T10:10:00+00:00', '2025-01-15T10:10:00+00:00');

            CREATE INDEX idx_transcription_track_id
                ON transcription_results(track_id);
            """
        )

        conn.commit()
        return conn

    def test_migration_allows_new_track_types(self, db_v15: sqlite3.Connection):
        """Test that migration allows 'music', 'sfx', 'non_speech' track_types."""
        from vpo.db.schema import migrate_v15_to_v16

        # Run migration
        migrate_v15_to_v16(db_v15)

        # Verify we can now insert new track_type values
        # First insert a new track for the transcription to reference
        db_v15.execute(
            "INSERT INTO tracks (id, file_id, track_type, language) "
            "VALUES (4, 1, 'audio', NULL)"
        )
        db_v15.execute(
            "INSERT INTO tracks (id, file_id, track_type, language) "
            "VALUES (5, 1, 'audio', NULL)"
        )
        db_v15.execute(
            "INSERT INTO tracks (id, file_id, track_type, language) "
            "VALUES (6, 1, 'audio', NULL)"
        )

        # Now insert transcription results with new track_types
        db_v15.execute(
            """
            INSERT INTO transcription_results (
                track_id, detected_language, confidence_score, track_type,
                transcript_sample, plugin_name, created_at, updated_at
            ) VALUES (
                4, NULL, 0.25, 'music',
                NULL, 'whisper-local',
                '2025-01-15T11:00:00+00:00', '2025-01-15T11:00:00+00:00'
            )
            """
        )
        db_v15.execute(
            """
            INSERT INTO transcription_results (
                track_id, detected_language, confidence_score, track_type,
                transcript_sample, plugin_name, created_at, updated_at
            ) VALUES (
                5, NULL, 0.15, 'sfx',
                NULL, 'whisper-local',
                '2025-01-15T11:01:00+00:00', '2025-01-15T11:01:00+00:00'
            )
            """
        )
        db_v15.execute(
            """
            INSERT INTO transcription_results (
                track_id, detected_language, confidence_score, track_type,
                transcript_sample, plugin_name, created_at, updated_at
            ) VALUES (
                6, NULL, 0.20, 'non_speech',
                '[Music]', 'whisper-local',
                '2025-01-15T11:02:00+00:00', '2025-01-15T11:02:00+00:00'
            )
            """
        )
        db_v15.commit()

        # Verify the new records exist
        cursor = db_v15.execute(
            "SELECT track_type FROM transcription_results WHERE track_id IN (4, 5, 6) "
            "ORDER BY track_id"
        )
        track_types = [row[0] for row in cursor.fetchall()]
        assert track_types == ["music", "sfx", "non_speech"]

    def test_migration_preserves_existing_data(self, db_v15: sqlite3.Connection):
        """Test that existing main/commentary/alternate records are preserved."""
        from vpo.db.schema import migrate_v15_to_v16

        # Run migration
        migrate_v15_to_v16(db_v15)

        # Check existing data is preserved
        cursor = db_v15.execute(
            "SELECT track_id, detected_language, confidence_score, track_type, "
            "transcript_sample, plugin_name FROM transcription_results "
            "ORDER BY track_id"
        )
        results = cursor.fetchall()

        assert len(results) == 3

        # Record 1: main track
        assert results[0][0] == 1  # track_id
        assert results[0][1] == "eng"  # detected_language
        assert results[0][2] == 0.95  # confidence_score
        assert results[0][3] == "main"  # track_type
        assert results[0][4] == "Hello world..."  # transcript_sample
        assert results[0][5] == "whisper-local"  # plugin_name

        # Record 2: commentary track
        assert results[1][0] == 2
        assert results[1][1] == "fre"
        assert results[1][3] == "commentary"

        # Record 3: alternate track
        assert results[2][0] == 3
        assert results[2][3] == "alternate"

    def test_migration_updates_schema_version(self, db_v15: sqlite3.Connection):
        """Test that schema version is updated to 16."""
        from vpo.db.schema import migrate_v15_to_v16

        # Run migration
        migrate_v15_to_v16(db_v15)

        # Check schema version updated
        cursor = db_v15.execute("SELECT value FROM _meta WHERE key = 'schema_version'")
        assert cursor.fetchone()[0] == "16"

    def test_migration_is_idempotent(self, db_v15: sqlite3.Connection):
        """Test that running migration twice doesn't error."""
        from vpo.db.schema import migrate_v15_to_v16

        # Run migration twice
        migrate_v15_to_v16(db_v15)
        migrate_v15_to_v16(db_v15)

        # Verify data is still correct
        cursor = db_v15.execute("SELECT COUNT(*) FROM transcription_results")
        assert cursor.fetchone()[0] == 3

        # Verify version is still 16
        cursor = db_v15.execute("SELECT value FROM _meta WHERE key = 'schema_version'")
        assert cursor.fetchone()[0] == "16"

    def test_migration_recreates_indexes(self, db_v15: sqlite3.Connection):
        """Test that indexes are recreated after migration."""
        from vpo.db.schema import migrate_v15_to_v16

        # Run migration
        migrate_v15_to_v16(db_v15)

        # Check that indexes exist
        cursor = db_v15.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='transcription_results'"
        )
        indexes = {row[0] for row in cursor.fetchall()}

        assert "idx_transcription_track_id" in indexes
        assert "idx_transcription_language" in indexes
        assert "idx_transcription_type" in indexes
        assert "idx_transcription_plugin" in indexes

    def test_migration_constraint_rejects_invalid_track_type(
        self, db_v15: sqlite3.Connection
    ):
        """Test that invalid track_type values are still rejected after migration."""
        from vpo.db.schema import migrate_v15_to_v16

        # Run migration
        migrate_v15_to_v16(db_v15)

        # Insert a track for FK constraint
        db_v15.execute(
            "INSERT INTO tracks (id, file_id, track_type) VALUES (10, 1, 'audio')"
        )

        # Attempt to insert an invalid track_type
        with pytest.raises(sqlite3.IntegrityError):
            db_v15.execute(
                """
                INSERT INTO transcription_results (
                    track_id, detected_language, confidence_score, track_type,
                    transcript_sample, plugin_name, created_at, updated_at
                ) VALUES (
                    10, 'eng', 0.5, 'invalid_type',
                    NULL, 'test',
                    '2025-01-15T12:00:00+00:00', '2025-01-15T12:00:00+00:00'
                )
                """
            )

    def test_migration_handles_empty_table(self, tmp_path: Path):
        """Test that migration works correctly on empty transcription_results table."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        # Create minimal v15 schema with empty transcription_results table
        conn.executescript(
            """
            CREATE TABLE _meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO _meta (key, value) VALUES ('schema_version', '15');
            CREATE TABLE files (id INTEGER PRIMARY KEY, path TEXT);
            INSERT INTO files (id, path) VALUES (1, '/test.mkv');
            CREATE TABLE tracks (
                id INTEGER PRIMARY KEY, file_id INTEGER
            );
            INSERT INTO tracks (id, file_id) VALUES (1, 1);
            CREATE TABLE transcription_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL UNIQUE,
                detected_language TEXT,
                confidence_score REAL NOT NULL,
                track_type TEXT NOT NULL DEFAULT 'main',
                transcript_sample TEXT,
                plugin_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CONSTRAINT valid_track_type CHECK (
                    track_type IN ('main', 'commentary', 'alternate')
                )
            );
            """
        )
        conn.commit()

        from vpo.db.schema import migrate_v15_to_v16

        # Run migration on empty table
        migrate_v15_to_v16(conn)

        # Should be able to insert new track_types
        conn.execute(
            """
            INSERT INTO transcription_results (
                track_id, detected_language, confidence_score, track_type,
                transcript_sample, plugin_name, created_at, updated_at
            ) VALUES (
                1, NULL, 0.10, 'non_speech',
                NULL, 'whisper-local',
                '2025-01-15T10:00:00+00:00', '2025-01-15T10:00:00+00:00'
            )
            """
        )
        conn.commit()

        cursor = conn.execute(
            "SELECT track_type FROM transcription_results WHERE track_id = 1"
        )
        assert cursor.fetchone()[0] == "non_speech"

        conn.close()


class TestMigrationV16ToV17:
    """Tests for v16 to v17 migration (plugin_metadata column)."""

    @pytest.fixture
    def db_v16(self, tmp_path: Path) -> sqlite3.Connection:
        """Create a database at version 16 without plugin_metadata column."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        # Create minimal v16 schema without plugin_metadata
        conn.executescript(
            """
            CREATE TABLE _meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            INSERT INTO _meta (key, value) VALUES ('schema_version', '16');

            CREATE TABLE files (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                directory TEXT NOT NULL,
                extension TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                modified_at TEXT NOT NULL,
                content_hash TEXT,
                container_format TEXT,
                scanned_at TEXT NOT NULL,
                scan_status TEXT NOT NULL DEFAULT 'pending',
                scan_error TEXT,
                job_id TEXT
            );
            INSERT INTO files (
                id, path, filename, directory, extension, size_bytes,
                modified_at, scanned_at, scan_status
            ) VALUES (
                1, '/test/movie.mkv', 'movie.mkv', '/test', '.mkv', 1000000,
                '2025-01-01T00:00:00Z', '2025-01-01T00:00:00Z', 'ok'
            );
            """
        )
        conn.commit()
        return conn

    def test_migration_adds_plugin_metadata_column(self, db_v16: sqlite3.Connection):
        """Test that migration adds plugin_metadata column."""
        from vpo.db.schema import migrate_v16_to_v17

        migrate_v16_to_v17(db_v16)

        cursor = db_v16.execute("PRAGMA table_info(files)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "plugin_metadata" in columns

    def test_migration_updates_schema_version(self, db_v16: sqlite3.Connection):
        """Test that schema version is updated to 17."""
        from vpo.db.schema import migrate_v16_to_v17

        migrate_v16_to_v17(db_v16)

        cursor = db_v16.execute("SELECT value FROM _meta WHERE key = 'schema_version'")
        assert cursor.fetchone()[0] == "17"

    def test_migration_is_idempotent(self, db_v16: sqlite3.Connection):
        """Test that running migration twice doesn't error."""
        from vpo.db.schema import migrate_v16_to_v17

        migrate_v16_to_v17(db_v16)
        migrate_v16_to_v17(db_v16)  # Should not raise

        cursor = db_v16.execute("SELECT value FROM _meta WHERE key = 'schema_version'")
        assert cursor.fetchone()[0] == "17"

    def test_migration_preserves_existing_data(self, db_v16: sqlite3.Connection):
        """Test that existing file records are preserved."""
        from vpo.db.schema import migrate_v16_to_v17

        migrate_v16_to_v17(db_v16)

        cursor = db_v16.execute(
            "SELECT path, filename, size_bytes FROM files WHERE id = 1"
        )
        row = cursor.fetchone()
        assert row[0] == "/test/movie.mkv"
        assert row[1] == "movie.mkv"
        assert row[2] == 1000000

    def test_plugin_metadata_accepts_json(self, db_v16: sqlite3.Connection):
        """Test that plugin_metadata column accepts JSON strings."""
        from vpo.db.schema import migrate_v16_to_v17

        migrate_v16_to_v17(db_v16)

        # Update with JSON data
        json_data = '{"radarr": {"original_language": "jpn", "year": 2024}}'
        db_v16.execute(
            "UPDATE files SET plugin_metadata = ? WHERE id = 1",
            (json_data,),
        )
        db_v16.commit()

        cursor = db_v16.execute("SELECT plugin_metadata FROM files WHERE id = 1")
        assert cursor.fetchone()[0] == json_data

    def test_plugin_metadata_null_by_default(self, db_v16: sqlite3.Connection):
        """Test that plugin_metadata is NULL for existing records after migration."""
        from vpo.db.schema import migrate_v16_to_v17

        migrate_v16_to_v17(db_v16)

        cursor = db_v16.execute("SELECT plugin_metadata FROM files WHERE id = 1")
        assert cursor.fetchone()[0] is None


class TestMigrationV19ToV20:
    """Tests for v19 to v20 migration (valid_priority constraint)."""

    @pytest.fixture
    def db_v19(self, tmp_path: Path) -> sqlite3.Connection:
        """Create a database at version 19 with test data."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        # Create minimal schema at v19 without valid_priority constraint
        conn.executescript(
            """
            CREATE TABLE _meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            INSERT INTO _meta (key, value) VALUES ('schema_version', '19');

            CREATE TABLE files (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE NOT NULL
            );
            INSERT INTO files (id, path) VALUES (1, '/test.mkv');

            CREATE TABLE jobs (
                id TEXT PRIMARY KEY,
                file_id INTEGER,
                file_path TEXT NOT NULL,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                priority INTEGER NOT NULL DEFAULT 100,
                policy_name TEXT,
                policy_json TEXT,
                progress_percent REAL NOT NULL DEFAULT 0.0,
                progress_json TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                worker_pid INTEGER,
                worker_heartbeat TEXT,
                output_path TEXT,
                backup_path TEXT,
                error_message TEXT,
                files_affected_json TEXT,
                summary_json TEXT,
                log_path TEXT,
                FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
                CONSTRAINT valid_status CHECK (
                    status IN ('queued', 'running', 'completed', 'failed', 'cancelled')
                ),
                CONSTRAINT valid_job_type CHECK (
                    job_type IN ('transcode', 'move', 'scan', 'apply')
                ),
                CONSTRAINT valid_progress CHECK (
                    progress_percent >= 0.0 AND progress_percent <= 100.0
                )
            );

            -- Insert jobs with various priorities (including out-of-range)
            INSERT INTO jobs (
                id, file_id, file_path, job_type, status, priority, created_at
            ) VALUES
                ('job-1', 1, '/test.mkv', 'scan', 'completed', 50, '2024-01-01'),
                ('job-2', 1, '/test.mkv', 'scan', 'completed', 100, '2024-01-01'),
                ('job-3', 1, '/test.mkv', 'scan', 'completed', -10, '2024-01-01'),
                ('job-4', 1, '/test.mkv', 'scan', 'completed', 2000, '2024-01-01');
            """
        )

        conn.commit()
        return conn

    def test_migration_adds_valid_priority_constraint(self, db_v19: sqlite3.Connection):
        """Test that migration adds the valid_priority constraint."""
        from vpo.db.schema import migrate_v19_to_v20

        # Run migration
        migrate_v19_to_v20(db_v19)

        # Check that constraint was added
        cursor = db_v19.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='jobs'"
        )
        schema = cursor.fetchone()[0]
        assert "valid_priority" in schema

        # Check schema version updated
        cursor = db_v19.execute("SELECT value FROM _meta WHERE key = 'schema_version'")
        assert cursor.fetchone()[0] == "20"

    def test_migration_clamps_out_of_range_priorities(self, db_v19: sqlite3.Connection):
        """Test that migration clamps priority values to 0-1000 range."""
        from vpo.db.schema import migrate_v19_to_v20

        # Run migration
        migrate_v19_to_v20(db_v19)

        # Check priorities were clamped
        cursor = db_v19.execute("SELECT id, priority FROM jobs ORDER BY id")
        jobs = cursor.fetchall()

        assert jobs[0][1] == 50  # Normal value - unchanged
        assert jobs[1][1] == 100  # Normal value - unchanged
        assert jobs[2][1] == 0  # -10 -> 0 (clamped)
        assert jobs[3][1] == 1000  # 2000 -> 1000 (clamped)

    def test_migration_is_idempotent(self, db_v19: sqlite3.Connection):
        """Test that running migration twice doesn't error."""
        from vpo.db.schema import migrate_v19_to_v20

        # Run migration twice
        migrate_v19_to_v20(db_v19)
        migrate_v19_to_v20(db_v19)

        # Verify schema version is still 20
        cursor = db_v19.execute("SELECT value FROM _meta WHERE key = 'schema_version'")
        assert cursor.fetchone()[0] == "20"

    def test_migration_preserves_job_data(self, db_v19: sqlite3.Connection):
        """Test that migration preserves all job data."""
        from vpo.db.schema import migrate_v19_to_v20

        # Run migration
        migrate_v19_to_v20(db_v19)

        # Verify all jobs still exist
        cursor = db_v19.execute("SELECT COUNT(*) FROM jobs")
        assert cursor.fetchone()[0] == 4

        # Verify job data preserved
        cursor = db_v19.execute(
            "SELECT job_type, status, file_path FROM jobs WHERE id = 'job-1'"
        )
        row = cursor.fetchone()
        assert row[0] == "scan"
        assert row[1] == "completed"
        assert row[2] == "/test.mkv"

    def test_constraint_rejects_invalid_priority(self, db_v19: sqlite3.Connection):
        """Test that constraint rejects new jobs with invalid priority."""
        from vpo.db.schema import migrate_v19_to_v20

        # Run migration
        migrate_v19_to_v20(db_v19)

        # Try to insert job with out-of-range priority
        with pytest.raises(sqlite3.IntegrityError):
            db_v19.execute(
                """
                INSERT INTO jobs (id, file_path, job_type, priority, created_at)
                VALUES ('job-bad', '/test.mkv', 'scan', 1001, '2024-01-01T00:00:00Z')
                """
            )

        with pytest.raises(sqlite3.IntegrityError):
            db_v19.execute(
                """
                INSERT INTO jobs (id, file_path, job_type, priority, created_at)
                VALUES ('job-bad', '/test.mkv', 'scan', -1, '2024-01-01T00:00:00Z')
                """
            )

    def test_constraint_accepts_valid_priority(self, db_v19: sqlite3.Connection):
        """Test that constraint accepts jobs with valid priority."""
        from vpo.db.schema import migrate_v19_to_v20

        # Run migration
        migrate_v19_to_v20(db_v19)

        # Insert job with valid priority values
        db_v19.execute(
            """
            INSERT INTO jobs (id, file_path, job_type, priority, created_at)
            VALUES ('job-low', '/test.mkv', 'scan', 0, '2024-01-01T00:00:00Z')
            """
        )
        db_v19.execute(
            """
            INSERT INTO jobs (id, file_path, job_type, priority, created_at)
            VALUES ('job-high', '/test.mkv', 'scan', 1000, '2024-01-01T00:00:00Z')
            """
        )
        db_v19.commit()

        # Verify jobs were inserted
        cursor = db_v19.execute("SELECT COUNT(*) FROM jobs")
        assert cursor.fetchone()[0] == 6  # 4 original + 2 new


class TestMigrationV21ToV22:
    """Tests for v21 to v22 migration (compound index for transcode report)."""

    @pytest.fixture
    def db_v21(self, tmp_path: Path) -> sqlite3.Connection:
        """Create a database at version 21 with processing_stats table."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        # Create minimal schema at v21 with processing_stats table
        conn.executescript(
            """
            CREATE TABLE _meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            INSERT INTO _meta (key, value) VALUES ('schema_version', '21');

            CREATE TABLE files (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE NOT NULL
            );
            INSERT INTO files (id, path) VALUES (1, '/test.mkv');

            CREATE TABLE processing_stats (
                id TEXT PRIMARY KEY,
                file_id INTEGER NOT NULL,
                processed_at TEXT NOT NULL,
                policy_name TEXT NOT NULL,
                size_before INTEGER NOT NULL,
                size_after INTEGER NOT NULL,
                size_change INTEGER NOT NULL,
                duration_seconds REAL NOT NULL,
                success INTEGER NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
            );

            -- Existing indexes from v21
            CREATE INDEX IF NOT EXISTS idx_stats_file ON processing_stats(file_id);
            CREATE INDEX IF NOT EXISTS idx_stats_policy
                ON processing_stats(policy_name);
            CREATE INDEX IF NOT EXISTS idx_stats_time
                ON processing_stats(processed_at DESC);
            CREATE INDEX IF NOT EXISTS idx_stats_success ON processing_stats(success);

            -- Insert test data
            INSERT INTO processing_stats (
                id, file_id, processed_at, policy_name,
                size_before, size_after, size_change,
                duration_seconds, success
            ) VALUES
                ('stat-1', 1, '2025-01-15T10:00:00Z', 'test.yaml',
                 1000000, 800000, 200000, 5.5, 1),
                ('stat-2', 1, '2025-01-15T11:00:00Z', 'test.yaml',
                 800000, 750000, 50000, 3.2, 1);
            """
        )

        conn.commit()
        return conn

    def test_migration_creates_compound_index(self, db_v21: sqlite3.Connection):
        """Test that migration creates idx_stats_file_time index."""
        from vpo.db.schema import migrate_v21_to_v22

        # Run migration
        migrate_v21_to_v22(db_v21)

        # Check that compound index exists
        cursor = db_v21.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='processing_stats' AND name='idx_stats_file_time'"
        )
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == "idx_stats_file_time"

    def test_migration_updates_schema_version(self, db_v21: sqlite3.Connection):
        """Test that schema version is updated to 22."""
        from vpo.db.schema import migrate_v21_to_v22

        # Run migration
        migrate_v21_to_v22(db_v21)

        # Check schema version updated
        cursor = db_v21.execute("SELECT value FROM _meta WHERE key = 'schema_version'")
        assert cursor.fetchone()[0] == "22"

    def test_migration_is_idempotent(self, db_v21: sqlite3.Connection):
        """Test that running migration twice doesn't error."""
        from vpo.db.schema import migrate_v21_to_v22

        # Run migration twice
        migrate_v21_to_v22(db_v21)
        migrate_v21_to_v22(db_v21)

        # Verify schema version is still 22
        cursor = db_v21.execute("SELECT value FROM _meta WHERE key = 'schema_version'")
        assert cursor.fetchone()[0] == "22"

        # Verify index still exists (only one)
        cursor = db_v21.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='index' "
            "AND name='idx_stats_file_time'"
        )
        assert cursor.fetchone()[0] == 1

    def test_migration_preserves_existing_data(self, db_v21: sqlite3.Connection):
        """Test that existing processing_stats records are preserved."""
        from vpo.db.schema import migrate_v21_to_v22

        # Run migration
        migrate_v21_to_v22(db_v21)

        # Verify data is preserved
        cursor = db_v21.execute("SELECT COUNT(*) FROM processing_stats")
        assert cursor.fetchone()[0] == 2

        cursor = db_v21.execute(
            "SELECT id, file_id, policy_name, size_change FROM processing_stats "
            "ORDER BY id"
        )
        rows = cursor.fetchall()
        assert rows[0] == ("stat-1", 1, "test.yaml", 200000)
        assert rows[1] == ("stat-2", 1, "test.yaml", 50000)

    def test_migration_preserves_existing_indexes(self, db_v21: sqlite3.Connection):
        """Test that existing indexes are preserved after migration."""
        from vpo.db.schema import migrate_v21_to_v22

        # Run migration
        migrate_v21_to_v22(db_v21)

        # Check that all original indexes still exist
        cursor = db_v21.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='processing_stats' ORDER BY name"
        )
        indexes = {row[0] for row in cursor.fetchall()}

        assert "idx_stats_file" in indexes
        assert "idx_stats_policy" in indexes
        assert "idx_stats_time" in indexes
        assert "idx_stats_success" in indexes
        assert "idx_stats_file_time" in indexes  # New compound index


class TestMigrationV22ToV23:
    """Tests for v22 to v23 migration (unified CLI/daemon job tracking)."""

    @pytest.fixture
    def db_v22(self, tmp_path: Path) -> sqlite3.Connection:
        """Create a database at version 22 with jobs and processing_stats tables."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        # Create minimal schema at v22 without origin, batch_id, job_id columns
        conn.executescript(
            """
            CREATE TABLE _meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            INSERT INTO _meta (key, value) VALUES ('schema_version', '22');

            CREATE TABLE files (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE NOT NULL
            );
            INSERT INTO files (id, path) VALUES (1, '/test.mkv');

            CREATE TABLE jobs (
                id TEXT PRIMARY KEY,
                file_id INTEGER,
                file_path TEXT NOT NULL,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                priority INTEGER NOT NULL DEFAULT 100,
                policy_name TEXT,
                policy_json TEXT,
                progress_percent REAL NOT NULL DEFAULT 0.0,
                progress_json TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                worker_pid INTEGER,
                worker_heartbeat TEXT,
                output_path TEXT,
                backup_path TEXT,
                error_message TEXT,
                files_affected_json TEXT,
                summary_json TEXT,
                log_path TEXT,
                FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
                CONSTRAINT valid_status CHECK (
                    status IN ('queued', 'running', 'completed', 'failed', 'cancelled')
                ),
                CONSTRAINT valid_job_type CHECK (
                    job_type IN ('transcode', 'move', 'scan', 'apply')
                )
            );

            CREATE TABLE processing_stats (
                id TEXT PRIMARY KEY,
                file_id INTEGER NOT NULL,
                processed_at TEXT NOT NULL,
                policy_name TEXT NOT NULL,
                size_before INTEGER NOT NULL,
                size_after INTEGER NOT NULL,
                size_change INTEGER NOT NULL,
                duration_seconds REAL NOT NULL,
                success INTEGER NOT NULL,
                encoder_type TEXT,
                FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
            );

            -- Insert test data
            INSERT INTO jobs (
                id, file_id, file_path, job_type, status, priority, created_at
            ) VALUES
                ('job-1', 1, '/test.mkv', 'scan', 'completed', 100, '2025-01-15');

            INSERT INTO processing_stats (
                id, file_id, processed_at, policy_name,
                size_before, size_after, size_change,
                duration_seconds, success
            ) VALUES
                ('stat-1', 1, '2025-01-15T10:00:00Z', 'test.yaml',
                 1000000, 800000, 200000, 5.5, 1);
            """
        )

        conn.commit()
        return conn

    def test_migration_adds_origin_column_to_jobs(self, db_v22: sqlite3.Connection):
        """Test that migration adds origin column to jobs table."""
        from vpo.db.schema import migrate_v22_to_v23

        # Run migration
        migrate_v22_to_v23(db_v22)

        # Check that origin column exists
        cursor = db_v22.execute("PRAGMA table_info(jobs)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "origin" in columns

    def test_migration_adds_batch_id_column_to_jobs(self, db_v22: sqlite3.Connection):
        """Test that migration adds batch_id column to jobs table."""
        from vpo.db.schema import migrate_v22_to_v23

        # Run migration
        migrate_v22_to_v23(db_v22)

        # Check that batch_id column exists
        cursor = db_v22.execute("PRAGMA table_info(jobs)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "batch_id" in columns

    def test_migration_adds_job_id_column_to_processing_stats(
        self, db_v22: sqlite3.Connection
    ):
        """Test that migration adds job_id column to processing_stats table."""
        from vpo.db.schema import migrate_v22_to_v23

        # Run migration
        migrate_v22_to_v23(db_v22)

        # Check that job_id column exists
        cursor = db_v22.execute("PRAGMA table_info(processing_stats)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "job_id" in columns

    def test_migration_creates_job_id_index(self, db_v22: sqlite3.Connection):
        """Test that migration creates idx_stats_job index."""
        from vpo.db.schema import migrate_v22_to_v23

        # Run migration
        migrate_v22_to_v23(db_v22)

        # Check that index exists
        cursor = db_v22.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='processing_stats' AND name='idx_stats_job'"
        )
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == "idx_stats_job"

    def test_migration_updates_schema_version(self, db_v22: sqlite3.Connection):
        """Test that schema version is updated to 23."""
        from vpo.db.schema import migrate_v22_to_v23

        # Run migration
        migrate_v22_to_v23(db_v22)

        # Check schema version updated
        cursor = db_v22.execute("SELECT value FROM _meta WHERE key = 'schema_version'")
        assert cursor.fetchone()[0] == "23"

    def test_migration_is_idempotent(self, db_v22: sqlite3.Connection):
        """Test that running migration twice doesn't error."""
        from vpo.db.schema import migrate_v22_to_v23

        # Run migration twice
        migrate_v22_to_v23(db_v22)
        migrate_v22_to_v23(db_v22)

        # Verify schema version is still 23
        cursor = db_v22.execute("SELECT value FROM _meta WHERE key = 'schema_version'")
        assert cursor.fetchone()[0] == "23"

    def test_migration_preserves_existing_job_data(self, db_v22: sqlite3.Connection):
        """Test that existing jobs records are preserved."""
        from vpo.db.schema import migrate_v22_to_v23

        # Run migration
        migrate_v22_to_v23(db_v22)

        # Verify job data is preserved
        cursor = db_v22.execute(
            "SELECT id, job_type, status, file_path FROM jobs WHERE id = 'job-1'"
        )
        row = cursor.fetchone()
        assert row[0] == "job-1"
        assert row[1] == "scan"
        assert row[2] == "completed"
        assert row[3] == "/test.mkv"

    def test_migration_preserves_existing_stats_data(self, db_v22: sqlite3.Connection):
        """Test that existing processing_stats records are preserved."""
        from vpo.db.schema import migrate_v22_to_v23

        # Run migration
        migrate_v22_to_v23(db_v22)

        # Verify stats data is preserved
        cursor = db_v22.execute(
            "SELECT id, policy_name, size_change FROM processing_stats "
            "WHERE id = 'stat-1'"
        )
        row = cursor.fetchone()
        assert row[0] == "stat-1"
        assert row[1] == "test.yaml"
        assert row[2] == 200000

    def test_process_job_type_requires_new_database(self, db_v22: sqlite3.Connection):
        """Test that 'process' job_type requires new database (constraint limitation).

        SQLite doesn't support modifying CHECK constraints after table creation.
        For existing databases, 'process' job type will be rejected. New databases
        created with schema v23 will allow 'process' job type.
        """
        from vpo.db.schema import migrate_v22_to_v23

        # Run migration
        migrate_v22_to_v23(db_v22)

        # Verify the old constraint still blocks 'process' in migrated databases
        # This is expected behavior - SQLite CHECK constraints can't be modified
        with pytest.raises(sqlite3.IntegrityError):
            db_v22.execute(
                """
                INSERT INTO jobs (
                    id, file_path, job_type, status, priority, created_at,
                    origin, batch_id
                ) VALUES (
                    'job-proc', '/test.mkv', 'process', 'running', 100,
                    '2025-01-15', 'cli', 'batch-123'
                )
                """
            )

    def test_new_database_allows_process_job_type(self, tmp_path: Path):
        """Test that new databases (v23) allow 'process' job_type."""
        from vpo.db.schema import create_schema

        # Create a fresh database with v23 schema
        db_path = tmp_path / "fresh.db"
        conn = sqlite3.connect(str(db_path))
        create_schema(conn)

        # Insert job with 'process' type - should work in new database
        conn.execute(
            """
            INSERT INTO files (path, filename, directory, extension, size_bytes,
                               modified_at, scanned_at, scan_status)
            VALUES ('/test.mkv', 'test.mkv', '/', '.mkv', 1000,
                    '2025-01-15T00:00:00Z', '2025-01-15T00:00:00Z', 'ok')
            """
        )
        conn.execute(
            """
            INSERT INTO jobs (id, file_path, job_type, status, priority, created_at,
                              origin, batch_id)
            VALUES ('job-proc', '/test.mkv', 'process', 'running', 100, '2025-01-15',
                    'cli', 'batch-123')
            """
        )
        conn.commit()

        cursor = conn.execute(
            "SELECT job_type, origin, batch_id FROM jobs WHERE id = 'job-proc'"
        )
        row = cursor.fetchone()
        assert row[0] == "process"
        assert row[1] == "cli"
        assert row[2] == "batch-123"

        conn.close()

    def test_migration_allows_stats_with_job_id(self, db_v22: sqlite3.Connection):
        """Test that processing_stats can be linked to jobs after migration."""
        from vpo.db.schema import migrate_v22_to_v23

        # Run migration
        migrate_v22_to_v23(db_v22)

        # Insert stats with job_id
        db_v22.execute(
            """
            INSERT INTO processing_stats (
                id, file_id, processed_at, policy_name,
                size_before, size_after, size_change,
                duration_seconds, success, job_id
            ) VALUES (
                'stat-2', 1, '2025-01-15T11:00:00Z', 'test.yaml',
                800000, 700000, 100000, 3.0, 1, 'job-1'
            )
            """
        )
        db_v22.commit()

        cursor = db_v22.execute(
            "SELECT id, job_id FROM processing_stats WHERE id = 'stat-2'"
        )
        row = cursor.fetchone()
        assert row[0] == "stat-2"
        assert row[1] == "job-1"

    def test_new_columns_are_null_by_default(self, db_v22: sqlite3.Connection):
        """Test that new columns are NULL for existing records."""
        from vpo.db.schema import migrate_v22_to_v23

        # Run migration
        migrate_v22_to_v23(db_v22)

        # Check jobs columns are NULL
        cursor = db_v22.execute("SELECT origin, batch_id FROM jobs WHERE id = 'job-1'")
        row = cursor.fetchone()
        assert row[0] is None  # origin
        assert row[1] is None  # batch_id

        # Check processing_stats job_id is NULL
        cursor = db_v22.execute(
            "SELECT job_id FROM processing_stats WHERE id = 'stat-1'"
        )
        row = cursor.fetchone()
        assert row[0] is None  # job_id


class TestMigrationV24ToV25:
    """Tests for v24→v25 migration (FK constraint on processing_stats.job_id)."""

    @pytest.fixture
    def db_v24(self, temp_db: Path) -> sqlite3.Connection:
        """Create a database at v24 schema version."""
        from vpo.db.schema import (
            migrate_v22_to_v23,
            migrate_v23_to_v24,
        )

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row

        # Create v22 schema (before job tracking unification)
        conn.executescript("""
            CREATE TABLE _meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO _meta (key, value) VALUES ('schema_version', '22');

            CREATE TABLE files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                directory TEXT NOT NULL,
                extension TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                modified_at TEXT NOT NULL,
                content_hash TEXT,
                container_format TEXT,
                scanned_at TEXT NOT NULL,
                scan_status TEXT NOT NULL DEFAULT 'pending',
                scan_error TEXT
            );

            CREATE TABLE jobs (
                id TEXT PRIMARY KEY,
                file_id INTEGER,
                file_path TEXT NOT NULL,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                priority INTEGER NOT NULL DEFAULT 100,
                policy_name TEXT,
                policy_json TEXT,
                progress_percent REAL NOT NULL DEFAULT 0.0,
                progress_json TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                worker_pid INTEGER,
                worker_heartbeat TEXT,
                output_path TEXT,
                backup_path TEXT,
                error_message TEXT,
                files_affected_json TEXT,
                summary_json TEXT,
                log_path TEXT,
                FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
            );

            CREATE TABLE processing_stats (
                id TEXT PRIMARY KEY,
                file_id INTEGER NOT NULL,
                processed_at TEXT NOT NULL,
                policy_name TEXT NOT NULL,
                size_before INTEGER NOT NULL,
                size_after INTEGER NOT NULL,
                size_change INTEGER NOT NULL,
                audio_tracks_before INTEGER NOT NULL DEFAULT 0,
                subtitle_tracks_before INTEGER NOT NULL DEFAULT 0,
                attachments_before INTEGER NOT NULL DEFAULT 0,
                audio_tracks_after INTEGER NOT NULL DEFAULT 0,
                subtitle_tracks_after INTEGER NOT NULL DEFAULT 0,
                attachments_after INTEGER NOT NULL DEFAULT 0,
                audio_tracks_removed INTEGER NOT NULL DEFAULT 0,
                subtitle_tracks_removed INTEGER NOT NULL DEFAULT 0,
                attachments_removed INTEGER NOT NULL DEFAULT 0,
                duration_seconds REAL NOT NULL,
                phases_completed INTEGER NOT NULL DEFAULT 0,
                phases_total INTEGER NOT NULL DEFAULT 0,
                total_changes INTEGER NOT NULL DEFAULT 0,
                video_source_codec TEXT,
                video_target_codec TEXT,
                video_transcode_skipped INTEGER NOT NULL DEFAULT 0,
                video_skip_reason TEXT,
                audio_tracks_transcoded INTEGER NOT NULL DEFAULT 0,
                audio_tracks_preserved INTEGER NOT NULL DEFAULT 0,
                hash_before TEXT,
                hash_after TEXT,
                success INTEGER NOT NULL,
                error_message TEXT,
                encoder_type TEXT,
                FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
            );

            -- Insert test data
            INSERT INTO files (
                id, path, filename, directory, extension,
                size_bytes, modified_at, scanned_at, scan_status
            ) VALUES (
                1, '/videos/test.mkv', 'test.mkv', '/videos', '.mkv',
                1000000, '2025-01-15T10:00:00Z', '2025-01-15T10:00:00Z', 'scanned'
            );

            INSERT INTO jobs (
                id, file_id, file_path, job_type, status, priority,
                created_at, started_at
            ) VALUES (
                'job-1', 1, '/videos/test.mkv', 'transcode', 'completed', 100,
                '2025-01-15T10:00:00Z', '2025-01-15T10:00:00Z'
            );

            INSERT INTO processing_stats (
                id, file_id, processed_at, policy_name,
                size_before, size_after, size_change,
                duration_seconds, success
            ) VALUES (
                'stat-1', 1, '2025-01-15T10:30:00Z', 'test.yaml',
                1000000, 900000, 100000, 5.0, 1
            );
        """)

        # Migrate to v23 (adds origin, batch_id, job_id columns)
        migrate_v22_to_v23(conn)

        # Migrate to v24 (adds indexes)
        migrate_v23_to_v24(conn)

        # Add some test data with job_id references
        conn.execute(
            """
            INSERT INTO processing_stats (
                id, file_id, processed_at, policy_name,
                size_before, size_after, size_change,
                duration_seconds, success, job_id
            ) VALUES (
                'stat-2', 1, '2025-01-15T11:00:00Z', 'test.yaml',
                800000, 700000, 100000, 3.0, 1, 'job-1'
            )
            """
        )
        # Add stats with orphaned job_id (references non-existent job)
        conn.execute(
            """
            INSERT INTO processing_stats (
                id, file_id, processed_at, policy_name,
                size_before, size_after, size_change,
                duration_seconds, success, job_id
            ) VALUES (
                'stat-orphan', 1, '2025-01-15T12:00:00Z', 'test.yaml',
                500000, 400000, 100000, 2.0, 1, 'nonexistent-job'
            )
            """
        )
        conn.commit()

        return conn

    def test_migration_adds_fk_constraint(self, db_v24: sqlite3.Connection):
        """Test that migration adds FK constraint on job_id."""
        from vpo.db.schema import migrate_v24_to_v25

        migrate_v24_to_v25(db_v24)

        # Check table SQL contains FK constraint
        cursor = db_v24.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type='table' AND name='processing_stats'"
        )
        row = cursor.fetchone()
        assert "REFERENCES jobs(id)" in row[0]
        assert "ON DELETE SET NULL" in row[0]

    def test_migration_updates_schema_version(self, db_v24: sqlite3.Connection):
        """Test that migration updates schema version to 25."""
        from vpo.db.schema import get_schema_version, migrate_v24_to_v25

        migrate_v24_to_v25(db_v24)

        version = get_schema_version(db_v24)
        assert version == 25

    def test_migration_preserves_existing_data(self, db_v24: sqlite3.Connection):
        """Test that migration preserves existing processing_stats data."""
        from vpo.db.schema import migrate_v24_to_v25

        migrate_v24_to_v25(db_v24)

        # Check stat-1 (no job_id) is preserved
        cursor = db_v24.execute(
            "SELECT id, file_id, policy_name, success, job_id "
            "FROM processing_stats WHERE id = 'stat-1'"
        )
        row = cursor.fetchone()
        assert row["id"] == "stat-1"
        assert row["file_id"] == 1
        assert row["policy_name"] == "test.yaml"
        assert row["success"] == 1
        assert row["job_id"] is None

        # Check stat-2 (with valid job_id) is preserved
        cursor = db_v24.execute(
            "SELECT id, job_id FROM processing_stats WHERE id = 'stat-2'"
        )
        row = cursor.fetchone()
        assert row["id"] == "stat-2"
        assert row["job_id"] == "job-1"

    def test_migration_nullifies_orphaned_job_ids(self, db_v24: sqlite3.Connection):
        """Test that migration sets orphaned job_ids to NULL."""
        from vpo.db.schema import migrate_v24_to_v25

        migrate_v24_to_v25(db_v24)

        # Check stat-orphan has job_id set to NULL
        cursor = db_v24.execute(
            "SELECT id, job_id FROM processing_stats WHERE id = 'stat-orphan'"
        )
        row = cursor.fetchone()
        assert row["id"] == "stat-orphan"
        assert row["job_id"] is None  # Was 'nonexistent-job', now NULL

    def test_migration_is_idempotent(self, db_v24: sqlite3.Connection):
        """Test that migration can be run multiple times safely."""
        from vpo.db.schema import migrate_v24_to_v25

        # Run migration twice
        migrate_v24_to_v25(db_v24)
        migrate_v24_to_v25(db_v24)

        # Should still be at version 25
        cursor = db_v24.execute("SELECT value FROM _meta WHERE key = 'schema_version'")
        row = cursor.fetchone()
        assert row[0] == "25"

    def test_migration_recreates_indexes(self, db_v24: sqlite3.Connection):
        """Test that migration recreates all indexes."""
        from vpo.db.schema import migrate_v24_to_v25

        migrate_v24_to_v25(db_v24)

        cursor = db_v24.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND tbl_name='processing_stats'"
        )
        indexes = {row[0] for row in cursor.fetchall()}

        assert "idx_stats_file" in indexes
        assert "idx_stats_job" in indexes
        assert "idx_stats_policy" in indexes
        assert "idx_stats_time" in indexes
        assert "idx_stats_success" in indexes
        assert "idx_stats_file_time" in indexes

    def test_fk_cascade_sets_null_on_job_delete(self, db_v24: sqlite3.Connection):
        """Test that deleting a job sets job_id to NULL in processing_stats."""
        from vpo.db.schema import migrate_v24_to_v25

        migrate_v24_to_v25(db_v24)

        # Enable foreign key enforcement (required for ON DELETE SET NULL)
        db_v24.execute("PRAGMA foreign_keys = ON")

        # Verify stat-2 has job_id = 'job-1'
        cursor = db_v24.execute(
            "SELECT job_id FROM processing_stats WHERE id = 'stat-2'"
        )
        row = cursor.fetchone()
        assert row["job_id"] == "job-1"

        # Delete job-1
        db_v24.execute("DELETE FROM jobs WHERE id = 'job-1'")
        db_v24.commit()

        # Verify job_id is now NULL (ON DELETE SET NULL)
        cursor = db_v24.execute(
            "SELECT job_id FROM processing_stats WHERE id = 'stat-2'"
        )
        row = cursor.fetchone()
        assert row["job_id"] is None
