"""Unit tests for database models."""

import sqlite3
from pathlib import Path


class TestFileOperations:
    """Tests for file database operations."""

    def test_insert_file(self, temp_db: Path):
        """Test inserting a new file record."""
        from vpo.db import (
            FileRecord,
            insert_file,
        )
        from vpo.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
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
        from vpo.db import (
            FileRecord,
            get_file_by_path,
            upsert_file,
        )
        from vpo.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
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

    def test_upsert_preserves_original_job_id(self, temp_db: Path):
        """Upserting a file preserves the original job_id from first scan."""
        from vpo.db import (
            FileRecord,
            get_file_by_path,
            upsert_file,
        )
        from vpo.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        create_schema(conn)

        # First scan sets job_id
        record = FileRecord(
            id=None,
            path="/media/video.mkv",
            filename="video.mkv",
            directory="/media",
            extension="mkv",
            size_bytes=1000000,
            modified_at="2024-01-01T00:00:00",
            content_hash=None,
            container_format="matroska",
            scanned_at="2024-01-01T00:00:00",
            scan_status="ok",
            scan_error=None,
            job_id="original-job-id",
        )
        upsert_file(conn, record)

        # Second scan with different job_id
        record.scanned_at = "2024-02-01T00:00:00"
        record.job_id = "newer-job-id"
        upsert_file(conn, record)

        # Original job_id should be preserved
        result = get_file_by_path(conn, "/media/video.mkv")
        assert result.job_id == "original-job-id"

        conn.close()

    def test_upsert_sets_job_id_when_null(self, temp_db: Path):
        """Upserting sets job_id if the existing record has no job_id."""
        from vpo.db import (
            FileRecord,
            get_file_by_path,
            upsert_file,
        )
        from vpo.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        create_schema(conn)

        # First insert with no job_id
        record = FileRecord(
            id=None,
            path="/media/video.mkv",
            filename="video.mkv",
            directory="/media",
            extension="mkv",
            size_bytes=1000000,
            modified_at="2024-01-01T00:00:00",
            content_hash=None,
            container_format="matroska",
            scanned_at="2024-01-01T00:00:00",
            scan_status="ok",
            scan_error=None,
            job_id=None,
        )
        upsert_file(conn, record)

        # Second scan provides a job_id
        record.job_id = "new-job-id"
        upsert_file(conn, record)

        # Should pick up the new job_id since original was NULL
        result = get_file_by_path(conn, "/media/video.mkv")
        assert result.job_id == "new-job-id"

        conn.close()

    def test_get_file_by_path(self, temp_db: Path):
        """Test retrieving a file by path."""
        from vpo.db import (
            FileRecord,
            get_file_by_path,
            insert_file,
        )
        from vpo.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
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
        from vpo.db import get_file_by_path
        from vpo.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        create_schema(conn)

        result = get_file_by_path(conn, "/nonexistent/path.mkv")
        assert result is None

        conn.close()

    def test_file_record_plugin_metadata_roundtrip(self, temp_db: Path):
        """Test FileRecord with plugin_metadata survives insert/get cycle."""
        import json

        from vpo.db import (
            FileRecord,
            get_file_by_id,
            insert_file,
        )
        from vpo.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        create_schema(conn)

        # Create FileRecord with plugin metadata
        plugin_metadata_json = json.dumps(
            {
                "radarr": {
                    "original_language": "jpn",
                    "tmdb_id": 8392,
                    "external_title": "My Neighbor Totoro",
                    "year": 1988,
                },
                "sonarr": None,
            }
        )

        file_record = FileRecord(
            id=None,
            path="/media/movie.mkv",
            filename="movie.mkv",
            directory="/media",
            extension="mkv",
            size_bytes=2000000,
            modified_at="2025-01-01T00:00:00",
            content_hash="xxh64:abc:def:2000000",
            container_format="matroska",
            scanned_at="2025-01-01T00:00:00",
            scan_status="ok",
            scan_error=None,
            plugin_metadata=plugin_metadata_json,
        )

        # Insert and retrieve
        file_id = insert_file(conn, file_record)
        retrieved = get_file_by_id(conn, file_id)

        assert retrieved is not None
        assert retrieved.plugin_metadata == plugin_metadata_json

        # Verify JSON is valid and contains expected data
        parsed = json.loads(retrieved.plugin_metadata)
        assert parsed["radarr"]["original_language"] == "jpn"
        assert parsed["radarr"]["tmdb_id"] == 8392
        assert parsed["radarr"]["external_title"] == "My Neighbor Totoro"
        assert parsed["radarr"]["year"] == 1988
        assert parsed["sonarr"] is None

        conn.close()

    def test_file_record_plugin_metadata_null(self, temp_db: Path):
        """Test FileRecord with null plugin_metadata."""
        from vpo.db import (
            FileRecord,
            get_file_by_id,
            insert_file,
        )
        from vpo.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        create_schema(conn)

        file_record = FileRecord(
            id=None,
            path="/media/movie.mkv",
            filename="movie.mkv",
            directory="/media",
            extension="mkv",
            size_bytes=1000000,
            modified_at="2025-01-01T00:00:00",
            content_hash="xxh64:abc:def:1000000",
            container_format="matroska",
            scanned_at="2025-01-01T00:00:00",
            scan_status="ok",
            scan_error=None,
            plugin_metadata=None,  # Explicitly null
        )

        file_id = insert_file(conn, file_record)
        retrieved = get_file_by_id(conn, file_id)

        assert retrieved is not None
        assert retrieved.plugin_metadata is None

        conn.close()


class TestTrackOperations:
    """Tests for track database operations."""

    def test_insert_track(self, temp_db: Path):
        """Test inserting a track record."""
        from vpo.db import (
            FileRecord,
            TrackRecord,
            insert_file,
            insert_track,
        )
        from vpo.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
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
        from vpo.db import (
            FileRecord,
            TrackRecord,
            get_tracks_for_file,
            insert_file,
            insert_track,
        )
        from vpo.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
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
                None,
                file_id,
                3,
                "subtitle",
                "subrip",
                "eng",
                "English Subs",
                True,
                False,
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
        from vpo.db import (
            FileRecord,
            TrackRecord,
            get_tracks_for_file,
            insert_file,
            insert_track,
        )
        from vpo.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
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
        from vpo.db import (
            FileRecord,
            TrackRecord,
            delete_file,
            insert_file,
            insert_track,
        )
        from vpo.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
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

        track = TrackRecord(None, file_id, 0, "video", "hevc", None, None, True, False)
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


class TestTrackRecordConversion:
    """Tests for TrackRecord bidirectional conversion methods."""

    def test_to_track_info_converts_all_fields(self) -> None:
        """Test that to_track_info converts all fields correctly."""
        from vpo.db import TrackInfo, TrackRecord

        track_record = TrackRecord(
            id=42,
            file_id=1,
            track_index=0,
            track_type="audio",
            codec="aac",
            language="eng",
            title="English Audio",
            is_default=True,
            is_forced=False,
            channels=6,
            channel_layout="5.1",
            width=None,
            height=None,
            frame_rate=None,
            color_transfer="smpte2084",
            color_primaries="bt2020",
            color_space="bt2020nc",
            color_range="tv",
            duration_seconds=7200.5,
        )

        track_info = track_record.to_track_info()

        assert isinstance(track_info, TrackInfo)
        assert track_info.id == 42
        assert track_info.index == 0
        assert track_info.track_type == "audio"
        assert track_info.codec == "aac"
        assert track_info.language == "eng"
        assert track_info.title == "English Audio"
        assert track_info.is_default is True
        assert track_info.is_forced is False
        assert track_info.channels == 6
        assert track_info.channel_layout == "5.1"
        assert track_info.width is None
        assert track_info.height is None
        assert track_info.frame_rate is None
        assert track_info.color_transfer == "smpte2084"
        assert track_info.color_primaries == "bt2020"
        assert track_info.color_space == "bt2020nc"
        assert track_info.color_range == "tv"
        assert track_info.duration_seconds == 7200.5

    def test_from_track_info_and_back(self) -> None:
        """Test round-trip conversion TrackInfo -> TrackRecord -> TrackInfo."""
        from vpo.db import TrackInfo, TrackRecord

        original = TrackInfo(
            index=1,
            track_type="video",
            codec="hevc",
            language=None,
            title="Main Video",
            is_default=True,
            is_forced=False,
            channels=None,
            channel_layout=None,
            width=1920,
            height=1080,
            frame_rate="23.976",
            color_transfer=None,
            color_primaries=None,
            color_space=None,
            color_range=None,
            duration_seconds=3600.0,
            id=None,
        )

        record = TrackRecord.from_track_info(original, file_id=99)
        # Simulate database assignment of ID
        record.id = 123
        converted = record.to_track_info()

        # All fields except id should match (id comes from database)
        assert converted.index == original.index
        assert converted.track_type == original.track_type
        assert converted.codec == original.codec
        assert converted.language == original.language
        assert converted.title == original.title
        assert converted.is_default == original.is_default
        assert converted.is_forced == original.is_forced
        assert converted.channels == original.channels
        assert converted.channel_layout == original.channel_layout
        assert converted.width == original.width
        assert converted.height == original.height
        assert converted.frame_rate == original.frame_rate
        assert converted.duration_seconds == original.duration_seconds
        assert converted.id == 123  # From database

    def test_tracks_to_track_info_batch_conversion(self) -> None:
        """Test tracks_to_track_info converts a list of records."""
        from vpo.db import (
            TrackRecord,
            tracks_to_track_info,
        )

        records = [
            TrackRecord(1, 1, 0, "video", "hevc", None, None, True, False),
            TrackRecord(2, 1, 1, "audio", "aac", "eng", "English", True, False),
            TrackRecord(3, 1, 2, "subtitle", "srt", "eng", "Subs", False, False),
        ]

        track_infos = tracks_to_track_info(records)

        assert len(track_infos) == 3
        assert track_infos[0].track_type == "video"
        assert track_infos[1].track_type == "audio"
        assert track_infos[2].track_type == "subtitle"
        assert track_infos[0].id == 1
        assert track_infos[1].id == 2
        assert track_infos[2].id == 3

    def test_tracks_to_track_info_empty_list(self) -> None:
        """Test tracks_to_track_info handles empty list."""
        from vpo.db import tracks_to_track_info

        result = tracks_to_track_info([])
        assert result == []
