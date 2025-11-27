"""Tests for typed view model dataclasses and functions."""

import sqlite3
from pathlib import Path


class TestFileListViewItem:
    """Tests for FileListViewItem dataclass."""

    def test_construction_from_dict(self):
        """Test FileListViewItem can be constructed from dict."""
        from video_policy_orchestrator.db.models import FileListViewItem

        data = {
            "id": 1,
            "path": "/test/video.mkv",
            "filename": "video.mkv",
            "scanned_at": "2024-01-01T00:00:00Z",
            "scan_status": "ok",
            "scan_error": None,
            "video_title": "Test Video",
            "width": 1920,
            "height": 1080,
            "audio_languages": "eng,ger",
        }
        item = FileListViewItem(**data)

        assert item.id == 1
        assert item.filename == "video.mkv"
        assert item.width == 1920
        assert item.height == 1080
        assert item.audio_languages == "eng,ger"

    def test_optional_fields_can_be_none(self):
        """Test FileListViewItem handles None optional fields."""
        from video_policy_orchestrator.db.models import FileListViewItem

        data = {
            "id": 1,
            "path": "/test/video.mkv",
            "filename": "video.mkv",
            "scanned_at": "2024-01-01T00:00:00Z",
            "scan_status": "ok",
            "scan_error": None,
            "video_title": None,
            "width": None,
            "height": None,
            "audio_languages": None,
        }
        item = FileListViewItem(**data)

        assert item.video_title is None
        assert item.width is None
        assert item.audio_languages is None


class TestLanguageOption:
    """Tests for LanguageOption dataclass."""

    def test_construction_from_dict(self):
        """Test LanguageOption can be constructed from dict."""
        from video_policy_orchestrator.db.models import LanguageOption

        data = {"code": "eng", "label": "eng"}
        option = LanguageOption(**data)

        assert option.code == "eng"
        assert option.label == "eng"


class TestTranscriptionListViewItem:
    """Tests for TranscriptionListViewItem dataclass."""

    def test_construction_from_dict(self):
        """Test TranscriptionListViewItem can be constructed from dict."""
        from video_policy_orchestrator.db.models import TranscriptionListViewItem

        data = {
            "id": 1,
            "filename": "video.mkv",
            "path": "/test/video.mkv",
            "scan_status": "ok",
            "transcription_count": 2,
            "detected_languages": "eng,ger",
            "avg_confidence": 0.95,
        }
        item = TranscriptionListViewItem(**data)

        assert item.id == 1
        assert item.transcription_count == 2
        assert item.avg_confidence == 0.95


class TestTranscriptionDetailView:
    """Tests for TranscriptionDetailView dataclass."""

    def test_construction_from_dict(self):
        """Test TranscriptionDetailView can be constructed from dict."""
        from video_policy_orchestrator.db.models import TranscriptionDetailView

        data = {
            "id": 1,
            "track_id": 10,
            "detected_language": "eng",
            "confidence_score": 0.95,
            "track_type": "audio",
            "transcript_sample": "Sample text...",
            "plugin_name": "whisper",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "track_index": 0,
            "codec": "aac",
            "original_language": "eng",
            "title": "English Audio",
            "channels": 2,
            "channel_layout": "stereo",
            "is_default": 1,
            "is_forced": 0,
            "file_id": 5,
            "filename": "video.mkv",
            "path": "/test/video.mkv",
        }
        item = TranscriptionDetailView(**data)

        assert item.id == 1
        assert item.detected_language == "eng"
        assert item.track_index == 0
        assert item.file_id == 5


class TestUpsertTracksHDR:
    """Tests for HDR metadata handling in upsert_tracks_for_file."""

    def test_upsert_tracks_updates_hdr_metadata(self, temp_db: Path):
        """Test that upsert_tracks_for_file updates HDR color metadata on re-scan."""
        from video_policy_orchestrator.db.models import (
            FileRecord,
            TrackInfo,
            get_tracks_for_file,
            insert_file,
            upsert_tracks_for_file,
        )
        from video_policy_orchestrator.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        create_schema(conn)

        # Insert file
        file_record = FileRecord(
            id=None,
            path="/test.mkv",
            filename="test.mkv",
            directory="/",
            extension="mkv",
            size_bytes=1000,
            modified_at="2024-01-01T00:00:00",
            content_hash="hash",
            container_format="matroska",
            scanned_at="2024-01-01T00:00:00",
            scan_status="ok",
            scan_error=None,
        )
        file_id = insert_file(conn, file_record)

        # Initial track without HDR metadata
        track_v1 = TrackInfo(
            index=0,
            track_type="video",
            codec="hevc",
            is_default=True,
            is_forced=False,
        )
        upsert_tracks_for_file(conn, file_id, [track_v1])
        conn.commit()

        # Verify no HDR data initially
        tracks = get_tracks_for_file(conn, file_id)
        assert len(tracks) == 1
        assert tracks[0].color_transfer is None

        # Update with HDR metadata (simulates re-scan with better introspection)
        track_v2 = TrackInfo(
            index=0,
            track_type="video",
            codec="hevc",
            is_default=True,
            is_forced=False,
            color_transfer="smpte2084",
            color_primaries="bt2020",
            color_space="bt2020nc",
            color_range="tv",
        )
        upsert_tracks_for_file(conn, file_id, [track_v2])
        conn.commit()

        # Verify HDR fields were updated
        tracks = get_tracks_for_file(conn, file_id)
        assert len(tracks) == 1
        assert tracks[0].color_transfer == "smpte2084"
        assert tracks[0].color_primaries == "bt2020"
        assert tracks[0].color_space == "bt2020nc"
        assert tracks[0].color_range == "tv"

        conn.close()

    def test_insert_track_with_hdr_metadata(self, temp_db: Path):
        """Test that new tracks are inserted with HDR color metadata."""
        from video_policy_orchestrator.db.models import (
            FileRecord,
            TrackInfo,
            get_tracks_for_file,
            insert_file,
            upsert_tracks_for_file,
        )
        from video_policy_orchestrator.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        create_schema(conn)

        # Insert file
        file_record = FileRecord(
            id=None,
            path="/hdr-video.mkv",
            filename="hdr-video.mkv",
            directory="/",
            extension="mkv",
            size_bytes=1000,
            modified_at="2024-01-01T00:00:00",
            content_hash="hash2",
            container_format="matroska",
            scanned_at="2024-01-01T00:00:00",
            scan_status="ok",
            scan_error=None,
        )
        file_id = insert_file(conn, file_record)

        # Insert track with HDR metadata directly
        track = TrackInfo(
            index=0,
            track_type="video",
            codec="hevc",
            is_default=True,
            is_forced=False,
            width=3840,
            height=2160,
            color_transfer="arib-std-b67",  # HLG
            color_primaries="bt2020",
            color_space="bt2020nc",
            color_range="tv",
        )
        upsert_tracks_for_file(conn, file_id, [track])
        conn.commit()

        # Verify HDR fields were inserted
        tracks = get_tracks_for_file(conn, file_id)
        assert len(tracks) == 1
        assert tracks[0].color_transfer == "arib-std-b67"
        assert tracks[0].color_primaries == "bt2020"

        conn.close()


class TestTypedFunctions:
    """Tests for typed query functions."""

    def test_get_files_filtered_typed_returns_dataclass(self, temp_db: Path):
        """Test get_files_filtered_typed returns FileListViewItem objects."""
        from video_policy_orchestrator.db.models import (
            FileListViewItem,
            FileRecord,
            TrackRecord,
            get_files_filtered_typed,
            insert_file,
            insert_track,
        )
        from video_policy_orchestrator.db.schema import create_schema

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

        # Add video track
        track = TrackRecord(
            id=None,
            file_id=file_id,
            track_index=0,
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
            duration_seconds=7200.0,
        )
        insert_track(conn, track)

        # Query
        result = get_files_filtered_typed(conn)

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], FileListViewItem)
        assert result[0].filename == "video.mkv"
        assert result[0].width == 1920

        conn.close()

    def test_get_files_filtered_typed_with_total(self, temp_db: Path):
        """Test get_files_filtered_typed returns tuple with total."""
        from video_policy_orchestrator.db.models import (
            FileListViewItem,
            FileRecord,
            get_files_filtered_typed,
            insert_file,
        )
        from video_policy_orchestrator.db.schema import create_schema

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        create_schema(conn)

        # Create two files
        for i in range(2):
            file_record = FileRecord(
                id=None,
                path=f"/media/video{i}.mkv",
                filename=f"video{i}.mkv",
                directory="/media",
                extension="mkv",
                size_bytes=1000000,
                modified_at="2024-01-01T00:00:00",
                content_hash=f"xxh64:abc:def:{i}",
                container_format="matroska",
                scanned_at="2024-01-01T00:00:00",
                scan_status="ok",
                scan_error=None,
            )
            insert_file(conn, file_record)

        # Query with return_total and limit
        result, total = get_files_filtered_typed(conn, limit=1, return_total=True)

        assert isinstance(result, list)
        assert len(result) == 1
        assert total == 2
        assert isinstance(result[0], FileListViewItem)

        conn.close()

    def test_get_distinct_audio_languages_typed(self, temp_db: Path):
        """Test get_distinct_audio_languages_typed returns LanguageOption objects."""
        from video_policy_orchestrator.db.models import (
            FileRecord,
            LanguageOption,
            TrackRecord,
            get_distinct_audio_languages_typed,
            insert_file,
            insert_track,
        )
        from video_policy_orchestrator.db.schema import create_schema

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

        # Add audio tracks with different languages
        for i, lang in enumerate(["eng", "ger"]):
            track = TrackRecord(
                id=None,
                file_id=file_id,
                track_index=i,
                track_type="audio",
                codec="aac",
                language=lang,
                title=None,
                is_default=False,
                is_forced=False,
            )
            insert_track(conn, track)

        # Query
        result = get_distinct_audio_languages_typed(conn)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, LanguageOption) for item in result)
        codes = [item.code for item in result]
        assert "eng" in codes
        assert "ger" in codes

        conn.close()
