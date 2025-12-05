"""Unit tests for track classification metadata functions."""

import pytest

from video_policy_orchestrator.db.types import DetectionMethod, FileRecord, TrackRecord
from video_policy_orchestrator.track_classification.metadata import (
    determine_original_track,
    get_original_language_from_metadata,
)


class TestGetOriginalLanguageFromMetadata:
    """Tests for get_original_language_from_metadata function."""

    def test_returns_none_when_no_metadata(self):
        """Should return None when no metadata sources available."""
        result = get_original_language_from_metadata()
        assert result is None

    def test_extracts_from_radarr_metadata(self):
        """Should extract original language from Radarr plugin data."""
        plugin_metadata = {"radarr": {"original_language": "en"}}
        result = get_original_language_from_metadata(plugin_metadata=plugin_metadata)
        assert result == "eng"

    def test_extracts_from_sonarr_metadata(self):
        """Should extract original language from Sonarr plugin data."""
        plugin_metadata = {"sonarr": {"original_language": "ja"}}
        result = get_original_language_from_metadata(plugin_metadata=plugin_metadata)
        assert result == "jpn"

    def test_extracts_from_tmdb_metadata(self):
        """Should extract original language from TMDB plugin data."""
        plugin_metadata = {"tmdb": {"original_language": "ko"}}
        result = get_original_language_from_metadata(plugin_metadata=plugin_metadata)
        assert result == "kor"

    def test_extracts_from_generic_top_level(self):
        """Should extract from generic original_language field."""
        plugin_metadata = {"original_language": "de"}
        result = get_original_language_from_metadata(plugin_metadata=plugin_metadata)
        assert result == "ger"

    def test_extracts_from_file_record_plugin_metadata(self):
        """Should extract from file record's plugin_metadata JSON."""
        file_record = FileRecord(
            id=1,
            path="/test/file.mkv",
            filename="file.mkv",
            directory="/test",
            extension=".mkv",
            size_bytes=1000,
            modified_at="2024-01-01T00:00:00Z",
            content_hash="abc123",
            container_format="matroska",
            scanned_at="2024-01-01T00:00:00Z",
            scan_status="completed",
            scan_error=None,
            job_id=None,
            plugin_metadata='{"radarr": {"original_language": "fr"}}',
        )
        result = get_original_language_from_metadata(file_record=file_record)
        assert result == "fre"

    def test_plugin_metadata_takes_priority_over_file_record(self):
        """Direct plugin_metadata should have priority over file record."""
        file_record = FileRecord(
            id=1,
            path="/test/file.mkv",
            filename="file.mkv",
            directory="/test",
            extension=".mkv",
            size_bytes=1000,
            modified_at="2024-01-01T00:00:00Z",
            content_hash="abc123",
            container_format="matroska",
            scanned_at="2024-01-01T00:00:00Z",
            scan_status="completed",
            scan_error=None,
            job_id=None,
            plugin_metadata='{"radarr": {"original_language": "fr"}}',
        )
        plugin_metadata = {"radarr": {"original_language": "en"}}
        result = get_original_language_from_metadata(
            file_record=file_record, plugin_metadata=plugin_metadata
        )
        assert result == "eng"  # plugin_metadata wins

    def test_handles_malformed_json_gracefully(self):
        """Should handle malformed JSON in file record gracefully."""
        file_record = FileRecord(
            id=1,
            path="/test/file.mkv",
            filename="file.mkv",
            directory="/test",
            extension=".mkv",
            size_bytes=1000,
            modified_at="2024-01-01T00:00:00Z",
            content_hash="abc123",
            container_format="matroska",
            scanned_at="2024-01-01T00:00:00Z",
            scan_status="completed",
            scan_error=None,
            job_id=None,
            plugin_metadata="{not valid json}",
        )
        result = get_original_language_from_metadata(file_record=file_record)
        assert result is None


class TestDetermineOriginalTrack:
    """Tests for determine_original_track function."""

    @pytest.fixture
    def make_audio_track(self):
        """Factory fixture for creating audio track records."""

        def _make(track_id: int, track_index: int, language: str | None = None):
            return TrackRecord(
                id=track_id,
                file_id=1,
                track_index=track_index,
                track_type="audio",
                codec="aac",
                language=language,
                title=None,
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

    def test_returns_none_for_empty_tracks(self):
        """Should return None when no tracks provided."""
        track_id, method, confidence = determine_original_track([])
        assert track_id is None
        assert confidence == 0.0

    def test_single_track_defaults_to_original(self, make_audio_track):
        """Single track should default to original with low confidence."""
        tracks = [make_audio_track(1, 0, "eng")]
        track_id, method, confidence = determine_original_track(tracks)
        assert track_id == 1
        assert method == DetectionMethod.POSITION
        assert confidence == 0.5

    def test_matches_track_by_original_language(self, make_audio_track):
        """Should match track with original language metadata."""
        tracks = [
            make_audio_track(1, 0, "eng"),
            make_audio_track(2, 1, "jpn"),
        ]
        track_id, method, confidence = determine_original_track(
            tracks, original_language="jpn"
        )
        assert track_id == 2
        assert method == DetectionMethod.METADATA
        assert confidence == 0.9

    def test_multiple_matches_selects_first(self, make_audio_track):
        """Multiple tracks matching should select first with lower confidence."""
        tracks = [
            make_audio_track(1, 0, "jpn"),
            make_audio_track(2, 1, "jpn"),  # Theatrical vs Extended
        ]
        track_id, method, confidence = determine_original_track(
            tracks, original_language="jpn"
        )
        assert track_id == 1
        assert method == DetectionMethod.METADATA
        assert confidence == 0.75

    def test_position_heuristic_when_no_language_match(self, make_audio_track):
        """Should fall back to position heuristic when no language match."""
        tracks = [
            make_audio_track(1, 0, "eng"),
            make_audio_track(2, 1, "spa"),
        ]
        track_id, method, confidence = determine_original_track(
            tracks,
            original_language="fra",  # No match
        )
        assert track_id == 1  # First track
        assert method == DetectionMethod.POSITION
        assert confidence == 0.6

    def test_position_heuristic_when_no_metadata(self, make_audio_track):
        """Should use position heuristic when no original language provided."""
        tracks = [
            make_audio_track(1, 0, "eng"),
            make_audio_track(2, 1, "spa"),
        ]
        track_id, method, confidence = determine_original_track(tracks)
        assert track_id == 1  # First track
        assert method == DetectionMethod.POSITION
        assert confidence == 0.6

    def test_uses_language_analysis_over_track_language(self, make_audio_track):
        """Should prefer language analysis result over track metadata."""
        tracks = [
            make_audio_track(1, 0, "und"),  # Undetermined in metadata
            make_audio_track(2, 1, "eng"),
        ]
        # Language analysis detected Japanese on track 1
        language_analysis = {1: "jpn", 2: "eng"}
        track_id, method, confidence = determine_original_track(
            tracks, original_language="jpn", language_analysis=language_analysis
        )
        assert track_id == 1
        assert method == DetectionMethod.METADATA
        assert confidence == 0.9
