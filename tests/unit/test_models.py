"""Unit tests for database models."""

import sqlite3
from pathlib import Path


class TestFileOperations:
    """Tests for file database operations."""

    def test_insert_file(self, temp_db: Path):
        """Test inserting a new file record."""
        from video_policy_orchestrator.db.models import (
            FileRecord,
            insert_file,
        )
        from video_policy_orchestrator.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.execute("PRAGMA foreign_keys = ON")
        create_schema(conn)

        file_record = FileRecord(
            id=None,
            path="/media/video.mkv",
            filename="video.mkv",
            directory="/media",
            extension="mkv",
            size_bytes=1000000,
            modified_at="2024-01-01T00:00:00",
            content_hash="xxh64:abc:def:1000000",
            container_format="matroska",
            scanned_at="2024-01-01T00:00:00",
            scan_status="ok",
            scan_error=None,
        )

        file_id = insert_file(conn, file_record)
        assert file_id is not None
        assert file_id > 0

        conn.close()

    def test_upsert_file_updates_existing(self, temp_db: Path):
        """Test that upserting a file with same path updates it."""
        from video_policy_orchestrator.db.models import (
            FileRecord,
            get_file_by_path,
            upsert_file,
        )
        from video_policy_orchestrator.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.execute("PRAGMA foreign_keys = ON")
        create_schema(conn)

        # Insert first version
        file_record = FileRecord(
            id=None,
            path="/media/video.mkv",
            filename="video.mkv",
            directory="/media",
            extension="mkv",
            size_bytes=1000000,
            modified_at="2024-01-01T00:00:00",
            content_hash="xxh64:abc:def:1000000",
            container_format="matroska",
            scanned_at="2024-01-01T00:00:00",
            scan_status="ok",
            scan_error=None,
        )

        file_id = upsert_file(conn, file_record)

        # Update with new size
        file_record.size_bytes = 2000000
        file_record.content_hash = "xxh64:new:hash:2000000"
        updated_id = upsert_file(conn, file_record)

        # Should be the same ID
        assert updated_id == file_id

        # Verify the update
        result = get_file_by_path(conn, "/media/video.mkv")
        assert result is not None
        assert result.size_bytes == 2000000
        assert result.content_hash == "xxh64:new:hash:2000000"

        conn.close()

    def test_get_file_by_path(self, temp_db: Path):
        """Test retrieving a file by path."""
        from video_policy_orchestrator.db.models import (
            FileRecord,
            get_file_by_path,
            insert_file,
        )
        from video_policy_orchestrator.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.execute("PRAGMA foreign_keys = ON")
        create_schema(conn)

        file_record = FileRecord(
            id=None,
            path="/media/video.mkv",
            filename="video.mkv",
            directory="/media",
            extension="mkv",
            size_bytes=1000000,
            modified_at="2024-01-01T00:00:00",
            content_hash="xxh64:abc:def:1000000",
            container_format="matroska",
            scanned_at="2024-01-01T00:00:00",
            scan_status="ok",
            scan_error=None,
        )

        insert_file(conn, file_record)

        result = get_file_by_path(conn, "/media/video.mkv")
        assert result is not None
        assert result.path == "/media/video.mkv"
        assert result.filename == "video.mkv"

        conn.close()

    def test_get_file_by_path_not_found(self, temp_db: Path):
        """Test that get_file_by_path returns None for non-existent file."""
        from video_policy_orchestrator.db.models import get_file_by_path
        from video_policy_orchestrator.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        create_schema(conn)

        result = get_file_by_path(conn, "/nonexistent/path.mkv")
        assert result is None

        conn.close()


class TestTrackOperations:
    """Tests for track database operations."""

    def test_insert_track(self, temp_db: Path):
        """Test inserting a track record."""
        from video_policy_orchestrator.db.models import (
            FileRecord,
            TrackRecord,
            insert_file,
            insert_track,
        )
        from video_policy_orchestrator.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.execute("PRAGMA foreign_keys = ON")
        create_schema(conn)

        # First create a file
        file_record = FileRecord(
            id=None,
            path="/media/video.mkv",
            filename="video.mkv",
            directory="/media",
            extension="mkv",
            size_bytes=1000000,
            modified_at="2024-01-01T00:00:00",
            content_hash="xxh64:abc:def:1000000",
            container_format="matroska",
            scanned_at="2024-01-01T00:00:00",
            scan_status="ok",
            scan_error=None,
        )
        file_id = insert_file(conn, file_record)

        # Now insert a track
        track_record = TrackRecord(
            id=None,
            file_id=file_id,
            track_index=0,
            track_type="video",
            codec="hevc",
            language=None,
            title="Main Video",
            is_default=True,
            is_forced=False,
        )

        track_id = insert_track(conn, track_record)
        assert track_id is not None
        assert track_id > 0

        conn.close()

    def test_insert_multiple_tracks(self, temp_db: Path):
        """Test inserting multiple tracks for a file."""
        from video_policy_orchestrator.db.models import (
            FileRecord,
            TrackRecord,
            get_tracks_for_file,
            insert_file,
            insert_track,
        )
        from video_policy_orchestrator.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.execute("PRAGMA foreign_keys = ON")
        create_schema(conn)

        # Create a file
        file_record = FileRecord(
            id=None,
            path="/media/video.mkv",
            filename="video.mkv",
            directory="/media",
            extension="mkv",
            size_bytes=1000000,
            modified_at="2024-01-01T00:00:00",
            content_hash="xxh64:abc:def:1000000",
            container_format="matroska",
            scanned_at="2024-01-01T00:00:00",
            scan_status="ok",
            scan_error=None,
        )
        file_id = insert_file(conn, file_record)

        # Insert multiple tracks
        tracks = [
            TrackRecord(
                None, file_id, 0, "video", "hevc", None, "Main Video", True, False
            ),
            TrackRecord(
                None, file_id, 1, "audio", "aac", "eng", "English Audio", True, False
            ),
            TrackRecord(
                None, file_id, 2, "audio", "aac", "jpn", "Japanese Audio", False, False
            ),
            TrackRecord(
                None, file_id, 3, "subtitle", "subrip", "eng", "English Subs",
                True, False
            ),
        ]

        for track in tracks:
            insert_track(conn, track)

        # Verify all tracks were inserted
        result_tracks = get_tracks_for_file(conn, file_id)
        assert len(result_tracks) == 4

        conn.close()

    def test_track_fields_per_fr010(self, temp_db: Path):
        """Test that track stores all fields required by FR-010."""
        from video_policy_orchestrator.db.models import (
            FileRecord,
            TrackRecord,
            get_tracks_for_file,
            insert_file,
            insert_track,
        )
        from video_policy_orchestrator.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.execute("PRAGMA foreign_keys = ON")
        create_schema(conn)

        # Create a file
        file_record = FileRecord(
            id=None,
            path="/media/video.mkv",
            filename="video.mkv",
            directory="/media",
            extension="mkv",
            size_bytes=1000000,
            modified_at="2024-01-01T00:00:00",
            content_hash="xxh64:abc:def:1000000",
            container_format="matroska",
            scanned_at="2024-01-01T00:00:00",
            scan_status="ok",
            scan_error=None,
        )
        file_id = insert_file(conn, file_record)

        # Insert track with all FR-010 fields
        track = TrackRecord(
            id=None,
            file_id=file_id,
            track_index=0,
            track_type="subtitle",
            codec="subrip",
            language="eng",
            title="English Subtitles",
            is_default=True,
            is_forced=True,
        )
        insert_track(conn, track)

        # Verify all fields are stored correctly
        tracks = get_tracks_for_file(conn, file_id)
        assert len(tracks) == 1
        result = tracks[0]

        assert result.track_index == 0
        assert result.track_type == "subtitle"
        assert result.codec == "subrip"
        assert result.language == "eng"
        assert result.title == "English Subtitles"
        assert result.is_default is True
        assert result.is_forced is True

        conn.close()

    def test_cascade_delete_tracks(self, temp_db: Path):
        """Test that tracks are deleted when file is deleted."""
        from video_policy_orchestrator.db.models import (
            FileRecord,
            TrackRecord,
            delete_file,
            insert_file,
            insert_track,
        )
        from video_policy_orchestrator.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.execute("PRAGMA foreign_keys = ON")
        create_schema(conn)

        # Create a file with tracks
        file_record = FileRecord(
            id=None,
            path="/media/video.mkv",
            filename="video.mkv",
            directory="/media",
            extension="mkv",
            size_bytes=1000000,
            modified_at="2024-01-01T00:00:00",
            content_hash="xxh64:abc:def:1000000",
            container_format="matroska",
            scanned_at="2024-01-01T00:00:00",
            scan_status="ok",
            scan_error=None,
        )
        file_id = insert_file(conn, file_record)

        track = TrackRecord(
            None, file_id, 0, "video", "hevc", None, None, True, False
        )
        insert_track(conn, track)

        # Delete the file
        delete_file(conn, file_id)

        # Verify tracks are also deleted
        cursor = conn.execute(
            "SELECT COUNT(*) FROM tracks WHERE file_id = ?", (file_id,)
        )
        count = cursor.fetchone()[0]
        assert count == 0

        conn.close()
