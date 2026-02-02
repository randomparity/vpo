"""Unit tests for FileOperationContext.

Tests the operation context that bridges FileInfo (domain model) and
operational needs (database IDs, track data with IDs).
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from vpo.db.types import FileInfo, TrackInfo
from vpo.workflow.phases.context import (
    FileOperationContext,
    OperationContext,
)


@pytest.fixture
def test_file(tmp_path):
    """Create a temporary test file."""
    f = tmp_path / "test.mkv"
    f.write_bytes(b"\x00" * 100)
    return f


def insert_test_file(
    conn: sqlite3.Connection,
    file_path: Path,
    container_format: str = "mkv",
) -> int:
    """Insert a test file record and return its ID."""
    cursor = conn.execute(
        """
        INSERT INTO files (
            path, filename, directory, extension, size_bytes,
            container_format, modified_at, scanned_at, scan_status
        )
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), 'complete')
        """,
        (
            str(file_path),
            file_path.name,
            str(file_path.parent),
            file_path.suffix,
            100,
            container_format,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def insert_test_track(
    conn: sqlite3.Connection,
    file_id: int,
    index: int,
    track_type: str,
    language: str = "eng",
    codec: str | None = None,
) -> int:
    """Insert a test track record and return its ID."""
    if codec is None:
        codec = {"video": "h264", "audio": "aac", "subtitle": "srt"}.get(
            track_type, "unknown"
        )
    cursor = conn.execute(
        """
        INSERT INTO tracks (
            file_id, track_index, track_type, codec, language
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (file_id, index, track_type, codec, language),
    )
    conn.commit()
    return cursor.lastrowid


class TestFileOperationContextFromFilePath:
    """Tests for FileOperationContext.from_file_path factory."""

    def test_creates_context_from_database(self, db_conn, test_file):
        """Creates context with file_id from database lookup."""
        file_id = insert_test_file(db_conn, test_file)
        insert_test_track(db_conn, file_id, 0, "video")
        insert_test_track(db_conn, file_id, 1, "audio", "eng")

        context = FileOperationContext.from_file_path(test_file, db_conn)

        assert context.file_id == str(file_id)
        assert context.file_path == test_file
        assert context.container == "mkv"
        assert len(context.tracks) == 2

    def test_tracks_have_database_ids(self, db_conn, test_file):
        """Tracks returned have their database IDs populated."""
        file_id = insert_test_file(db_conn, test_file)
        track_id_1 = insert_test_track(db_conn, file_id, 0, "video")
        track_id_2 = insert_test_track(db_conn, file_id, 1, "audio", "eng")

        context = FileOperationContext.from_file_path(test_file, db_conn)

        assert context.tracks[0].id == track_id_1
        assert context.tracks[1].id == track_id_2

    def test_raises_for_unknown_file(self, db_conn, test_file):
        """Raises ValueError if file not in database."""
        with pytest.raises(ValueError, match="File not in database"):
            FileOperationContext.from_file_path(test_file, db_conn)

    def test_handles_missing_container_format(self, db_conn, test_file):
        """Falls back to 'unknown' if container_format is None."""
        # Insert file with NULL container_format
        conn = db_conn
        conn.execute(
            """
            INSERT INTO files (
                path, filename, directory, extension, size_bytes,
                container_format, modified_at, scanned_at, scan_status
            )
            VALUES (?, ?, ?, ?, ?, NULL, datetime('now'), datetime('now'), 'complete')
            """,
            (
                str(test_file),
                test_file.name,
                str(test_file.parent),
                test_file.suffix,
                100,
            ),
        )
        conn.commit()

        context = FileOperationContext.from_file_path(test_file, db_conn)

        assert context.container == "unknown"


class TestFileOperationContextFromFileInfo:
    """Tests for FileOperationContext.from_file_info factory."""

    def test_creates_context_from_file_info(self, db_conn, test_file):
        """Creates context from FileInfo with DB lookup for ID."""
        file_id = insert_test_file(db_conn, test_file, "mp4")
        insert_test_track(db_conn, file_id, 0, "video")

        file_info = FileInfo(
            path=test_file,
            filename=test_file.name,
            directory=test_file.parent,
            extension=test_file.suffix,
            size_bytes=100,
            modified_at=datetime.now(timezone.utc),
            container_format="mp4",
            tracks=[
                TrackInfo(index=0, track_type="video", codec="h264"),
            ],
        )

        context = FileOperationContext.from_file_info(file_info, db_conn)

        assert context.file_id == str(file_id)
        assert context.file_path == test_file
        assert context.container == "mp4"

    def test_gets_tracks_from_database(self, db_conn, test_file):
        """Retrieves tracks from database, not from FileInfo."""
        file_id = insert_test_file(db_conn, test_file)
        track_id = insert_test_track(db_conn, file_id, 0, "audio", "eng")

        # FileInfo has no tracks
        file_info = FileInfo(
            path=test_file,
            filename=test_file.name,
            directory=test_file.parent,
            extension=test_file.suffix,
            size_bytes=100,
            modified_at=datetime.now(timezone.utc),
            container_format="mkv",
            tracks=[],  # Empty!
        )

        context = FileOperationContext.from_file_info(file_info, db_conn)

        # Should have track from database, not FileInfo
        assert len(context.tracks) == 1
        assert context.tracks[0].id == track_id
        assert context.tracks[0].track_type == "audio"

    def test_raises_for_unknown_file(self, db_conn, test_file):
        """Raises ValueError if file not in database."""
        file_info = FileInfo(
            path=test_file,
            filename=test_file.name,
            directory=test_file.parent,
            extension=test_file.suffix,
            size_bytes=100,
            modified_at=datetime.now(timezone.utc),
            container_format="mkv",
            tracks=[],
        )

        with pytest.raises(ValueError, match="File not in database"):
            FileOperationContext.from_file_info(file_info, db_conn)

    def test_uses_file_info_container_format(self, db_conn, test_file):
        """Uses container_format from FileInfo, not database."""
        # Database has "mkv"
        insert_test_file(db_conn, test_file, "mkv")

        # FileInfo has "mp4"
        file_info = FileInfo(
            path=test_file,
            filename=test_file.name,
            directory=test_file.parent,
            extension=test_file.suffix,
            size_bytes=100,
            modified_at=datetime.now(timezone.utc),
            container_format="mp4",
            tracks=[],
        )

        context = FileOperationContext.from_file_info(file_info, db_conn)

        # Should use FileInfo's container_format
        assert context.container == "mp4"


class TestOperationContextProtocol:
    """Tests verifying FileOperationContext satisfies OperationContext protocol."""

    def test_implements_protocol_properties(self, db_conn, test_file):
        """FileOperationContext has all required protocol properties."""
        file_id = insert_test_file(db_conn, test_file)
        insert_test_track(db_conn, file_id, 0, "audio")

        context = FileOperationContext.from_file_path(test_file, db_conn)

        # Verify all protocol properties exist and return correct types
        assert isinstance(context.file_id, str)
        assert isinstance(context.file_path, Path)
        assert isinstance(context.container, str)
        assert isinstance(context.tracks, list)
        assert all(isinstance(t, TrackInfo) for t in context.tracks)

    def test_protocol_typing(self, db_conn, test_file):
        """FileOperationContext can be assigned to OperationContext type."""
        file_id = insert_test_file(db_conn, test_file)

        context = FileOperationContext.from_file_path(test_file, db_conn)

        # This should type-check correctly
        op_context: OperationContext = context

        # And still work
        assert op_context.file_id == str(file_id)
