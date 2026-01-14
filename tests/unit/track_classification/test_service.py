"""Unit tests for track classification service."""

import pytest

from vpo.db.types import (
    CommentaryStatus,
    DetectionMethod,
    FileRecord,
    OriginalDubbedStatus,
    TrackRecord,
)
from vpo.track_classification.models import AcousticProfile
from vpo.track_classification.service import (
    _is_commentary_by_acoustic,
    _is_commentary_by_metadata,
    classify_track,
)


class TestIsCommentaryByMetadata:
    """Tests for _is_commentary_by_metadata helper."""

    @pytest.fixture
    def make_track(self):
        """Factory fixture for creating audio tracks."""

        def _make(title: str | None = None):
            return TrackRecord(
                id=1,
                file_id=1,
                track_index=0,
                track_type="audio",
                codec="aac",
                language="eng",
                title=title,
                is_default=False,
                is_forced=False,
                channels=2,
                channel_layout="stereo",
                width=None,
                height=None,
                frame_rate=None,
                color_transfer=None,
                color_primaries=None,
                color_space=None,
                color_range=None,
                duration_seconds=None,
            )

        return _make

    def test_returns_false_for_no_title(self, make_track):
        """Should return False when track has no title."""
        track = make_track(None)
        assert _is_commentary_by_metadata(track) is False

    def test_returns_false_for_regular_title(self, make_track):
        """Should return False for regular audio track titles."""
        track = make_track("English 5.1 Surround")
        assert _is_commentary_by_metadata(track) is False

    def test_detects_commentary_keyword(self, make_track):
        """Should detect 'commentary' keyword in title."""
        track = make_track("Director's Commentary")
        assert _is_commentary_by_metadata(track) is True

    def test_detects_audio_commentary_keyword(self, make_track):
        """Should detect 'audio commentary' in title."""
        track = make_track("Audio Commentary with Cast")
        assert _is_commentary_by_metadata(track) is True

    def test_case_insensitive(self, make_track):
        """Should match keywords case-insensitively."""
        track = make_track("COMMENTARY")
        assert _is_commentary_by_metadata(track) is True

    def test_detects_making_of_keyword(self, make_track):
        """Should detect 'making of' keyword."""
        track = make_track("Making of Documentary Audio")
        assert _is_commentary_by_metadata(track) is True


class TestIsCommentaryByAcoustic:
    """Tests for _is_commentary_by_acoustic helper."""

    def test_high_speech_density_and_low_dynamic_range(self):
        """High speech density + low dynamic range = commentary."""
        profile = AcousticProfile(
            speech_density=0.8,
            avg_pause_duration=2.0,
            voice_count_estimate=2,
            dynamic_range_db=12.0,
            has_background_audio=True,
        )
        assert _is_commentary_by_acoustic(profile) is True

    def test_low_speech_density(self):
        """Low speech density should not indicate commentary."""
        profile = AcousticProfile(
            speech_density=0.2,
            avg_pause_duration=5.0,
            voice_count_estimate=10,
            dynamic_range_db=30.0,
            has_background_audio=False,
        )
        assert _is_commentary_by_acoustic(profile) is False

    def test_high_dynamic_range(self):
        """High dynamic range (movie audio) should not be commentary."""
        profile = AcousticProfile(
            speech_density=0.3,
            avg_pause_duration=3.0,
            voice_count_estimate=5,
            dynamic_range_db=35.0,
            has_background_audio=False,
        )
        assert _is_commentary_by_acoustic(profile) is False

    def test_moderate_indicators(self):
        """Moderate values should be borderline."""
        # Just below threshold
        profile = AcousticProfile(
            speech_density=0.55,
            avg_pause_duration=2.5,
            voice_count_estimate=2,
            dynamic_range_db=18.0,
            has_background_audio=False,
        )
        # This should be just below 0.5 threshold
        result = _is_commentary_by_acoustic(profile)
        # 0.2 (speech) + 0.15 (dynamic) + 0.2 (voices) = 0.55 >= 0.5
        assert result is True

    def test_many_voices_not_commentary(self):
        """Many distinct voices indicates movie audio, not commentary."""
        profile = AcousticProfile(
            speech_density=0.4,
            avg_pause_duration=1.0,
            voice_count_estimate=10,
            dynamic_range_db=25.0,
            has_background_audio=False,
        )
        assert _is_commentary_by_acoustic(profile) is False


class TestClassifyTrack:
    """Integration tests for classify_track function."""

    @pytest.fixture
    def db_conn(self, tmp_path):
        """Create an in-memory database with schema."""
        import sqlite3

        from vpo.db.schema import create_schema

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        create_schema(conn)
        return conn

    @pytest.fixture
    def file_record(self):
        """Create a test file record."""
        return FileRecord(
            id=1,
            path="/test/movie.mkv",
            filename="movie.mkv",
            directory="/test",
            extension=".mkv",
            size_bytes=1000000,
            modified_at="2024-01-01T00:00:00Z",
            content_hash="testhash123",
            container_format="matroska",
            scanned_at="2024-01-01T00:00:00Z",
            scan_status="completed",
            scan_error=None,
            job_id=None,
            plugin_metadata=None,
        )

    @pytest.fixture
    def make_audio_track(self):
        """Factory for audio track records."""

        def _make(
            track_id: int,
            track_index: int,
            language: str | None = None,
            title: str | None = None,
        ):
            return TrackRecord(
                id=track_id,
                file_id=1,
                track_index=track_index,
                track_type="audio",
                codec="aac",
                language=language,
                title=title,
                is_default=False,
                is_forced=False,
                channels=2,
                channel_layout="stereo",
                width=None,
                height=None,
                frame_rate=None,
                color_transfer=None,
                color_primaries=None,
                color_space=None,
                color_range=None,
                duration_seconds=None,
            )

        return _make

    def test_classifies_original_track_by_language(
        self, db_conn, file_record, make_audio_track
    ):
        """Should classify track as original when language matches metadata."""
        track = make_audio_track(1, 0, "jpn")
        all_tracks = [track, make_audio_track(2, 1, "eng")]

        result = classify_track(
            conn=db_conn,
            track=track,
            file_record=file_record,
            original_language="jpn",
            all_audio_tracks=all_tracks,
        )

        assert result.original_dubbed_status == OriginalDubbedStatus.ORIGINAL
        assert result.detection_method == DetectionMethod.METADATA
        assert result.confidence >= 0.9

    def test_classifies_dubbed_track(self, db_conn, file_record, make_audio_track):
        """Should classify track as dubbed when different from original."""
        track = make_audio_track(2, 1, "eng")
        all_tracks = [make_audio_track(1, 0, "jpn"), track]

        result = classify_track(
            conn=db_conn,
            track=track,
            file_record=file_record,
            original_language="jpn",
            all_audio_tracks=all_tracks,
        )

        assert result.original_dubbed_status == OriginalDubbedStatus.DUBBED
        assert result.detection_method == DetectionMethod.METADATA

    def test_detects_commentary_by_title(self, db_conn, file_record, make_audio_track):
        """Should detect commentary from track title."""
        track = make_audio_track(1, 0, "eng", "Director's Commentary")

        result = classify_track(
            conn=db_conn,
            track=track,
            file_record=file_record,
            all_audio_tracks=[track],
        )

        assert result.commentary_status == CommentaryStatus.COMMENTARY
        assert result.confidence >= 0.85

    def test_raises_for_non_audio_track(self, db_conn, file_record):
        """Should raise error for non-audio tracks."""
        from vpo.track_classification import ClassificationError

        video_track = TrackRecord(
            id=1,
            file_id=1,
            track_index=0,
            track_type="video",
            codec="hevc",
            language=None,
            title=None,
            is_default=True,
            is_forced=False,
            channels=None,
            channel_layout=None,
            width=1920,
            height=1080,
            frame_rate="24000/1001",
            color_transfer=None,
            color_primaries=None,
            color_space=None,
            color_range=None,
            duration_seconds=None,
        )

        with pytest.raises(ClassificationError, match="non-audio track"):
            classify_track(
                conn=db_conn,
                track=video_track,
                file_record=file_record,
            )
