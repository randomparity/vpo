"""Unit tests verifying CRUD functions do not auto-commit.

These tests ensure that simple CRUD functions in queries.py do NOT call
conn.commit(), allowing callers to manage transactions explicitly. This
enables atomic multi-operation transactions.
"""

import sqlite3
import uuid
from datetime import datetime, timezone

import pytest

from vpo.db.queries import (
    delete_file,
    delete_job,
    delete_old_jobs,
    delete_tracks_for_file,
    insert_file,
    insert_job,
    insert_track,
    update_job_progress,
    update_job_status,
    upsert_file,
)
from vpo.db.schema import create_schema
from vpo.db.types import FileRecord, Job, JobStatus, JobType, TrackRecord


@pytest.fixture
def test_conn() -> sqlite3.Connection:
    """Create an in-memory database for testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    return conn


@pytest.fixture
def second_conn() -> sqlite3.Connection:
    """Create a second in-memory database connection for testing.

    Note: In SQLite, in-memory databases are connection-local, so we can't
    use this to test visibility across connections. For proper testing,
    we need to use a file-based database.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    return conn


def make_test_file_record(path: str = "/test/video.mkv") -> FileRecord:
    """Create a test FileRecord."""
    return FileRecord(
        id=None,
        path=path,
        filename="video.mkv",
        directory="/test",
        extension="mkv",
        size_bytes=1000,
        modified_at=datetime.now(timezone.utc).isoformat(),
        content_hash="abc123",
        container_format="Matroska",
        scanned_at=datetime.now(timezone.utc).isoformat(),
        scan_status="ok",
        scan_error=None,
    )


def make_test_track_record(file_id: int) -> TrackRecord:
    """Create a test TrackRecord."""
    return TrackRecord(
        id=None,
        file_id=file_id,
        track_index=0,
        track_type="video",
        codec="h264",
        language="eng",
        title=None,
        is_default=True,
        is_forced=False,
    )


def make_test_job() -> Job:
    """Create a test Job."""
    return Job(
        id=str(uuid.uuid4()),
        file_id=None,
        file_path="/test/video.mkv",
        job_type=JobType.TRANSCODE,
        status=JobStatus.QUEUED,
        priority=100,
        policy_name="test-policy",
        policy_json="{}",
        progress_percent=0.0,
        progress_json=None,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


class TestInsertFileNoCommit:
    """Tests that insert_file does not auto-commit."""

    def test_insert_file_does_not_commit(self, test_conn: sqlite3.Connection) -> None:
        """insert_file should not commit the transaction."""
        record = make_test_file_record()

        # Insert file
        file_id = insert_file(test_conn, record)
        assert file_id is not None

        # Verify file exists in current connection
        cursor = test_conn.execute("SELECT path FROM files WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "/test/video.mkv"

        # Rollback should undo the insert
        test_conn.rollback()

        # Verify file no longer exists
        cursor = test_conn.execute("SELECT path FROM files WHERE id = ?", (file_id,))
        assert cursor.fetchone() is None


class TestUpsertFileNoCommit:
    """Tests that upsert_file does not auto-commit."""

    def test_upsert_file_does_not_commit(self, test_conn: sqlite3.Connection) -> None:
        """upsert_file should not commit the transaction."""
        record = make_test_file_record()

        # Upsert file
        file_id = upsert_file(test_conn, record)
        assert file_id is not None

        # Verify file exists in current connection
        cursor = test_conn.execute("SELECT path FROM files WHERE id = ?", (file_id,))
        assert cursor.fetchone() is not None

        # Rollback should undo the upsert
        test_conn.rollback()

        # Verify file no longer exists
        cursor = test_conn.execute("SELECT path FROM files WHERE id = ?", (file_id,))
        assert cursor.fetchone() is None


class TestDeleteFileNoCommit:
    """Tests that delete_file does not auto-commit."""

    def test_delete_file_does_not_commit(self, test_conn: sqlite3.Connection) -> None:
        """delete_file should not commit the transaction."""
        record = make_test_file_record()
        file_id = insert_file(test_conn, record)
        test_conn.commit()  # Commit the insert first

        # Delete file
        delete_file(test_conn, file_id)

        # Verify file is deleted in current connection
        cursor = test_conn.execute("SELECT path FROM files WHERE id = ?", (file_id,))
        assert cursor.fetchone() is None

        # Rollback should undo the delete
        test_conn.rollback()

        # Verify file exists again
        cursor = test_conn.execute("SELECT path FROM files WHERE id = ?", (file_id,))
        assert cursor.fetchone() is not None


class TestInsertTrackNoCommit:
    """Tests that insert_track does not auto-commit."""

    def test_insert_track_does_not_commit(self, test_conn: sqlite3.Connection) -> None:
        """insert_track should not commit the transaction."""
        # First create a file
        file_record = make_test_file_record()
        file_id = insert_file(test_conn, file_record)
        test_conn.commit()

        # Insert track
        track_record = make_test_track_record(file_id)
        track_id = insert_track(test_conn, track_record)
        assert track_id is not None

        # Verify track exists in current connection
        cursor = test_conn.execute("SELECT id FROM tracks WHERE id = ?", (track_id,))
        assert cursor.fetchone() is not None

        # Rollback should undo the insert
        test_conn.rollback()

        # Verify track no longer exists
        cursor = test_conn.execute("SELECT id FROM tracks WHERE id = ?", (track_id,))
        assert cursor.fetchone() is None


class TestDeleteTracksForFileNoCommit:
    """Tests that delete_tracks_for_file does not auto-commit."""

    def test_delete_tracks_for_file_does_not_commit(
        self, test_conn: sqlite3.Connection
    ) -> None:
        """delete_tracks_for_file should not commit the transaction."""
        # Create file and track
        file_record = make_test_file_record()
        file_id = insert_file(test_conn, file_record)
        track_record = make_test_track_record(file_id)
        track_id = insert_track(test_conn, track_record)
        test_conn.commit()

        # Delete tracks
        delete_tracks_for_file(test_conn, file_id)

        # Verify track is deleted in current connection
        cursor = test_conn.execute("SELECT id FROM tracks WHERE id = ?", (track_id,))
        assert cursor.fetchone() is None

        # Rollback should undo the delete
        test_conn.rollback()

        # Verify track exists again
        cursor = test_conn.execute("SELECT id FROM tracks WHERE id = ?", (track_id,))
        assert cursor.fetchone() is not None


class TestInsertJobNoCommit:
    """Tests that insert_job does not auto-commit."""

    def test_insert_job_does_not_commit(self, test_conn: sqlite3.Connection) -> None:
        """insert_job should not commit the transaction."""
        job = make_test_job()

        # Insert job
        job_id = insert_job(test_conn, job)
        assert job_id == job.id

        # Verify job exists in current connection
        cursor = test_conn.execute("SELECT id FROM jobs WHERE id = ?", (job_id,))
        assert cursor.fetchone() is not None

        # Rollback should undo the insert
        test_conn.rollback()

        # Verify job no longer exists
        cursor = test_conn.execute("SELECT id FROM jobs WHERE id = ?", (job_id,))
        assert cursor.fetchone() is None


class TestUpdateJobStatusNoCommit:
    """Tests that update_job_status does not auto-commit."""

    def test_update_job_status_does_not_commit(
        self, test_conn: sqlite3.Connection
    ) -> None:
        """update_job_status should not commit the transaction."""
        job = make_test_job()
        insert_job(test_conn, job)
        test_conn.commit()

        # Update job status
        update_job_status(test_conn, job.id, JobStatus.RUNNING)

        # Verify status is updated in current connection
        cursor = test_conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()
        assert row[0] == "running"

        # Rollback should undo the update
        test_conn.rollback()

        # Verify status reverted
        cursor = test_conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,))
        row = cursor.fetchone()
        assert row[0] == "queued"


class TestUpdateJobProgressNoCommit:
    """Tests that update_job_progress does not auto-commit."""

    def test_update_job_progress_does_not_commit(
        self, test_conn: sqlite3.Connection
    ) -> None:
        """update_job_progress should not commit the transaction."""
        job = make_test_job()
        insert_job(test_conn, job)
        test_conn.commit()

        # Update job progress
        update_job_progress(test_conn, job.id, 50.0)

        # Verify progress is updated in current connection
        cursor = test_conn.execute(
            "SELECT progress_percent FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row[0] == 50.0

        # Rollback should undo the update
        test_conn.rollback()

        # Verify progress reverted
        cursor = test_conn.execute(
            "SELECT progress_percent FROM jobs WHERE id = ?", (job.id,)
        )
        row = cursor.fetchone()
        assert row[0] == 0.0


class TestDeleteJobNoCommit:
    """Tests that delete_job does not auto-commit."""

    def test_delete_job_does_not_commit(self, test_conn: sqlite3.Connection) -> None:
        """delete_job should not commit the transaction."""
        job = make_test_job()
        insert_job(test_conn, job)
        test_conn.commit()

        # Delete job
        delete_job(test_conn, job.id)

        # Verify job is deleted in current connection
        cursor = test_conn.execute("SELECT id FROM jobs WHERE id = ?", (job.id,))
        assert cursor.fetchone() is None

        # Rollback should undo the delete
        test_conn.rollback()

        # Verify job exists again
        cursor = test_conn.execute("SELECT id FROM jobs WHERE id = ?", (job.id,))
        assert cursor.fetchone() is not None


class TestDeleteOldJobsNoCommit:
    """Tests that delete_old_jobs does not auto-commit."""

    def test_delete_old_jobs_does_not_commit(
        self, test_conn: sqlite3.Connection
    ) -> None:
        """delete_old_jobs should not commit the transaction."""
        # Create an old completed job
        job = make_test_job()
        job = Job(
            id=job.id,
            file_id=None,
            file_path=job.file_path,
            job_type=job.job_type,
            status=JobStatus.COMPLETED,
            priority=job.priority,
            policy_name=job.policy_name,
            policy_json=job.policy_json,
            progress_percent=100.0,
            progress_json=None,
            created_at="2020-01-01T00:00:00Z",  # Old date
        )
        insert_job(test_conn, job)
        test_conn.commit()

        # Delete old jobs
        cutoff = datetime.now(timezone.utc).isoformat()
        count = delete_old_jobs(test_conn, cutoff)
        assert count == 1

        # Verify job is deleted in current connection
        cursor = test_conn.execute("SELECT id FROM jobs WHERE id = ?", (job.id,))
        assert cursor.fetchone() is None

        # Rollback should undo the delete
        test_conn.rollback()

        # Verify job exists again
        cursor = test_conn.execute("SELECT id FROM jobs WHERE id = ?", (job.id,))
        assert cursor.fetchone() is not None
