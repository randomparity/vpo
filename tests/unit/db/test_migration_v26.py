"""Tests for schema migration v25 to v26."""

import sqlite3

import pytest

from vpo.db.schema.definition import SCHEMA_VERSION, create_schema
from vpo.db.schema.migrations.v26_to_v30 import migrate_v25_to_v26


@pytest.fixture
def v25_conn():
    """Create a v25 database (before migration)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    # Downgrade version to 25 so migration can run
    conn.execute("UPDATE _meta SET value = '25' WHERE key = 'schema_version'")
    conn.commit()
    return conn


class TestSchemaVersion:
    """Tests for schema version constants."""

    def test_schema_version_is_26(self):
        assert SCHEMA_VERSION == 26


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
