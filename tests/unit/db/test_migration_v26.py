"""Tests for schema migration v25 to v26 and v26 to v27."""

import sqlite3

import pytest

from vpo.db.schema.definition import SCHEMA_VERSION, create_schema
from vpo.db.schema.migrations.v26_to_v30 import migrate_v25_to_v26, migrate_v26_to_v27


def _create_v25_schema(conn: sqlite3.Connection) -> None:
    """Build a genuine v25 database (jobs table without 'prune' type).

    This creates the essential tables with the v25 CHECK constraint
    that does NOT include 'prune', so the migration's rebuild path
    actually executes.
    """
    conn.executescript("""
        CREATE TABLE _meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        INSERT INTO _meta (key, value) VALUES ('schema_version', '25');

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
            scan_error TEXT,
            job_id TEXT,
            plugin_metadata TEXT
        );

        -- v25 jobs table: CHECK constraint does NOT include 'prune'
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
            error_message TEXT,
            output_path TEXT,
            summary_json TEXT,
            worker_pid INTEGER,
            worker_heartbeat TEXT,
            backup_path TEXT,
            files_affected_json TEXT,
            log_path TEXT,
            origin TEXT,
            batch_id TEXT,

            FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
            CONSTRAINT valid_status CHECK (
                status IN ('queued', 'running', 'completed', 'failed', 'cancelled')
            ),
            CONSTRAINT valid_job_type CHECK (
                job_type IN ('transcode', 'move', 'scan', 'apply', 'process')
            ),
            CONSTRAINT valid_progress CHECK (
                progress_percent >= 0.0 AND progress_percent <= 100.0
            ),
            CONSTRAINT valid_priority CHECK (
                priority >= 0 AND priority <= 1000
            )
        );

        CREATE INDEX idx_jobs_status ON jobs(status);
        CREATE INDEX idx_jobs_file_id ON jobs(file_id);
        CREATE INDEX idx_jobs_created_at ON jobs(created_at);
    """)


@pytest.fixture
def v25_conn():
    """Create a v25 database (before migration).

    This builds a genuine v25 schema where:
    - jobs table CHECK constraint does NOT include 'prune'
    - library_snapshots table does NOT exist
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _create_v25_schema(conn)
    return conn


class TestSchemaVersion:
    """Tests for schema version constants."""

    def test_schema_version_is_27(self):
        assert SCHEMA_VERSION == 27


class TestMigrateV25ToV26:
    """Tests for the v25→v26 migration."""

    def test_creates_library_snapshots_table(self, v25_conn):
        """Migration creates the library_snapshots table."""
        migrate_v25_to_v26(v25_conn)

        # Verify table exists by inserting a row
        v25_conn.execute(
            "INSERT INTO library_snapshots "
            "(snapshot_at, total_files, total_size_bytes, "
            "missing_files, error_files) "
            "VALUES ('2025-01-01T00:00:00Z', 100, 50000000, 5, 2)"
        )
        v25_conn.commit()

        cursor = v25_conn.execute(
            "SELECT total_files, missing_files FROM library_snapshots"
        )
        row = cursor.fetchone()
        assert row["total_files"] == 100
        assert row["missing_files"] == 5

    def test_updates_schema_version_to_26(self, v25_conn):
        """Migration updates schema version to 26."""
        migrate_v25_to_v26(v25_conn)

        cursor = v25_conn.execute(
            "SELECT value FROM _meta WHERE key = 'schema_version'"
        )
        assert cursor.fetchone()[0] == "26"

    def test_migration_is_idempotent(self, v25_conn):
        """Running the migration twice does not fail."""
        migrate_v25_to_v26(v25_conn)
        # Reset version to trigger re-run logic
        v25_conn.execute("UPDATE _meta SET value = '25' WHERE key = 'schema_version'")
        v25_conn.commit()
        migrate_v25_to_v26(v25_conn)

        cursor = v25_conn.execute(
            "SELECT value FROM _meta WHERE key = 'schema_version'"
        )
        assert cursor.fetchone()[0] == "26"

    def test_prune_job_type_allowed(self, v25_conn):
        """After migration, 'prune' job_type is allowed in jobs table."""
        migrate_v25_to_v26(v25_conn)

        # Insert a job with type 'prune'
        v25_conn.execute(
            "INSERT INTO jobs (id, file_path, job_type, status, "
            "priority, progress_percent, created_at) "
            "VALUES ('test-id', '/test', 'prune', 'queued', "
            "100, 0.0, '2025-01-01T00:00:00Z')"
        )
        v25_conn.commit()

        cursor = v25_conn.execute("SELECT job_type FROM jobs WHERE id = 'test-id'")
        assert cursor.fetchone()[0] == "prune"

    def test_prune_job_type_rejected_before_migration(self, v25_conn):
        """Before migration, 'prune' job_type is rejected by CHECK constraint."""
        with pytest.raises(sqlite3.IntegrityError):
            v25_conn.execute(
                "INSERT INTO jobs (id, file_path, job_type, status, "
                "priority, progress_percent, created_at) "
                "VALUES ('test-id', '/test', 'prune', 'queued', "
                "100, 0.0, '2025-01-01T00:00:00Z')"
            )

    def test_migration_preserves_existing_jobs(self, v25_conn):
        """Existing job rows survive the table rebuild."""
        # Insert jobs before migration
        v25_conn.execute(
            "INSERT INTO jobs (id, file_path, job_type, status, "
            "priority, progress_percent, created_at, policy_name, "
            "error_message, origin, batch_id) "
            "VALUES ('job-1', '/media/a.mkv', 'transcode', 'completed', "
            "100, 100.0, '2025-01-01T00:00:00Z', 'my-policy', "
            "NULL, 'cli', 'batch-abc')"
        )
        v25_conn.execute(
            "INSERT INTO jobs (id, file_path, job_type, status, "
            "priority, progress_percent, created_at, worker_pid, "
            "summary_json) "
            "VALUES ('job-2', '/media/b.mkv', 'scan', 'running', "
            "50, 25.0, '2025-01-02T00:00:00Z', 12345, "
            "'{\"files_scanned\": 10}')"
        )
        v25_conn.commit()

        migrate_v25_to_v26(v25_conn)

        # Verify all rows survived
        cursor = v25_conn.execute(
            "SELECT id, file_path, job_type, status, priority, "
            "progress_percent, policy_name, error_message, origin, "
            "batch_id, worker_pid, summary_json "
            "FROM jobs ORDER BY id"
        )
        rows = cursor.fetchall()
        assert len(rows) == 2

        # Check first job
        assert rows[0]["id"] == "job-1"
        assert rows[0]["job_type"] == "transcode"
        assert rows[0]["status"] == "completed"
        assert rows[0]["policy_name"] == "my-policy"
        assert rows[0]["origin"] == "cli"
        assert rows[0]["batch_id"] == "batch-abc"

        # Check second job
        assert rows[1]["id"] == "job-2"
        assert rows[1]["job_type"] == "scan"
        assert rows[1]["worker_pid"] == 12345
        assert rows[1]["summary_json"] == '{"files_scanned": 10}'

    def test_migration_recreates_all_indexes(self, v25_conn):
        """Migration creates all canonical indexes from definition.py."""
        migrate_v25_to_v26(v25_conn)

        cursor = v25_conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'index' AND tbl_name = 'jobs' "
            "AND name LIKE 'idx_jobs_%' "
            "ORDER BY name"
        )
        index_names = sorted(row[0] for row in cursor.fetchall())

        expected_indexes = sorted(
            [
                "idx_jobs_batch_id",
                "idx_jobs_created_at",
                "idx_jobs_file_id",
                "idx_jobs_job_type",
                "idx_jobs_origin",
                "idx_jobs_priority_created",
                "idx_jobs_status",
            ]
        )
        assert index_names == expected_indexes

    def test_migration_rebuild_path_executes(self, v25_conn):
        """After migration, jobs_new table does not exist (was renamed)."""
        migrate_v25_to_v26(v25_conn)

        cursor = v25_conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'jobs_new'"
        )
        assert cursor.fetchone() is None

        # But jobs table does exist
        cursor = v25_conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'jobs'"
        )
        assert cursor.fetchone() is not None

    def test_no_library_snapshots_before_migration(self, v25_conn):
        """v25 database does not have library_snapshots table."""
        cursor = v25_conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name = 'library_snapshots'"
        )
        assert cursor.fetchone() is None


class TestFreshSchema:
    """Tests that a fresh schema includes v26 features."""

    def test_fresh_schema_has_library_snapshots(self):
        """Fresh database includes library_snapshots table."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        create_schema(conn)

        conn.execute(
            "INSERT INTO library_snapshots "
            "(snapshot_at, total_files, total_size_bytes, "
            "missing_files, error_files) "
            "VALUES ('2025-01-01T00:00:00Z', 50, 10000000, 3, 1)"
        )
        conn.commit()

        cursor = conn.execute("SELECT COUNT(*) FROM library_snapshots")
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_fresh_schema_allows_prune_job_type(self):
        """Fresh database allows 'prune' job_type."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        create_schema(conn)

        conn.execute(
            "INSERT INTO jobs (id, file_path, job_type, status, "
            "priority, progress_percent, created_at) "
            "VALUES ('test-id', '/test', 'prune', 'queued', "
            "100, 0.0, '2025-01-01T00:00:00Z')"
        )
        conn.commit()

        cursor = conn.execute("SELECT job_type FROM jobs WHERE id = 'test-id'")
        assert cursor.fetchone()[0] == "prune"
        conn.close()


def _create_v26_schema(conn: sqlite3.Connection) -> None:
    """Build a v26 database (after v25→v26 migration but before v27)."""
    _create_v25_schema(conn)
    migrate_v25_to_v26(conn)


@pytest.fixture
def v26_conn():
    """Create a v26 database (before v26→v27 migration)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _create_v26_schema(conn)
    return conn


class TestMigrateV26ToV27:
    """Tests for the v26→v27 migration."""

    def test_container_tags_column_exists(self, v26_conn):
        """Migration adds container_tags column to files table."""
        migrate_v26_to_v27(v26_conn)

        cursor = v26_conn.execute("PRAGMA table_info(files)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "container_tags" in columns

    def test_updates_schema_version_to_27(self, v26_conn):
        """Migration updates schema version to 27."""
        migrate_v26_to_v27(v26_conn)

        cursor = v26_conn.execute(
            "SELECT value FROM _meta WHERE key = 'schema_version'"
        )
        assert cursor.fetchone()[0] == "27"

    def test_migration_is_idempotent(self, v26_conn):
        """Running the migration twice does not fail."""
        migrate_v26_to_v27(v26_conn)
        # Reset version to trigger re-run
        v26_conn.execute("UPDATE _meta SET value = '26' WHERE key = 'schema_version'")
        v26_conn.commit()
        migrate_v26_to_v27(v26_conn)

        cursor = v26_conn.execute(
            "SELECT value FROM _meta WHERE key = 'schema_version'"
        )
        assert cursor.fetchone()[0] == "27"

    def test_existing_file_records_preserved(self, v26_conn):
        """Existing file records are preserved after migration."""
        v26_conn.execute(
            "INSERT INTO files (path, filename, directory, extension, "
            "size_bytes, modified_at, scanned_at, scan_status) "
            "VALUES ('/test/video.mkv', 'video.mkv', '/test', 'mkv', "
            "1000000, '2025-01-01T00:00:00Z', '2025-01-01T00:00:00Z', 'ok')"
        )
        v26_conn.commit()

        migrate_v26_to_v27(v26_conn)

        cursor = v26_conn.execute("SELECT path, filename FROM files")
        row = cursor.fetchone()
        assert row["path"] == "/test/video.mkv"
        assert row["filename"] == "video.mkv"

    def test_container_tags_read_write(self, v26_conn):
        """container_tags can be written and read after migration."""
        v26_conn.execute(
            "INSERT INTO files (path, filename, directory, extension, "
            "size_bytes, modified_at, scanned_at, scan_status) "
            "VALUES ('/test/video.mkv', 'video.mkv', '/test', 'mkv', "
            "1000000, '2025-01-01T00:00:00Z', '2025-01-01T00:00:00Z', 'ok')"
        )
        v26_conn.commit()

        migrate_v26_to_v27(v26_conn)

        v26_conn.execute(
            "UPDATE files SET container_tags = ? WHERE path = ?",
            ('{"title": "My Movie"}', "/test/video.mkv"),
        )
        v26_conn.commit()

        cursor = v26_conn.execute(
            "SELECT container_tags FROM files WHERE path = ?",
            ("/test/video.mkv",),
        )
        assert cursor.fetchone()[0] == '{"title": "My Movie"}'
