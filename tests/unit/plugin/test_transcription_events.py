"""Tests for transcription event types and validation.

Tests for GitHub Issue #230: Plugin Infrastructure Extension.
"""

from pathlib import Path
from unittest.mock import MagicMock

from vpo.plugin.events import (
    ANALYZER_EVENTS,
    TRANSCRIPTION_COMPLETED,
    TRANSCRIPTION_REQUESTED,
    VALID_EVENTS,
    TranscriptionCompletedEvent,
    TranscriptionRequestedEvent,
    is_analyzer_event,
    is_valid_event,
)
from vpo.plugin_sdk import (
    create_transcription_completed_event,
    create_transcription_requested_event,
    mock_track_info,
)


class TestTranscriptionEventConstants:
    """Tests for transcription event constants."""

    def test_transcription_requested_value(self) -> None:
        """TRANSCRIPTION_REQUESTED has correct string value."""
        assert TRANSCRIPTION_REQUESTED == "transcription.requested"

    def test_transcription_completed_value(self) -> None:
        """TRANSCRIPTION_COMPLETED has correct string value."""
        assert TRANSCRIPTION_COMPLETED == "transcription.completed"

    def test_transcription_requested_in_valid_events(self) -> None:
        """TRANSCRIPTION_REQUESTED is in VALID_EVENTS."""
        assert TRANSCRIPTION_REQUESTED in VALID_EVENTS

    def test_transcription_completed_in_valid_events(self) -> None:
        """TRANSCRIPTION_COMPLETED is in VALID_EVENTS."""
        assert TRANSCRIPTION_COMPLETED in VALID_EVENTS

    def test_transcription_requested_in_analyzer_events(self) -> None:
        """TRANSCRIPTION_REQUESTED is in ANALYZER_EVENTS."""
        assert TRANSCRIPTION_REQUESTED in ANALYZER_EVENTS

    def test_transcription_completed_in_analyzer_events(self) -> None:
        """TRANSCRIPTION_COMPLETED is in ANALYZER_EVENTS."""
        assert TRANSCRIPTION_COMPLETED in ANALYZER_EVENTS


class TestTranscriptionEventValidation:
    """Tests for event validation functions."""

    def test_is_valid_event_transcription_requested(self) -> None:
        """is_valid_event returns True for transcription.requested."""
        assert is_valid_event("transcription.requested") is True

    def test_is_valid_event_transcription_completed(self) -> None:
        """is_valid_event returns True for transcription.completed."""
        assert is_valid_event("transcription.completed") is True

    def test_is_analyzer_event_transcription_requested(self) -> None:
        """is_analyzer_event returns True for transcription.requested."""
        assert is_analyzer_event("transcription.requested") is True

    def test_is_analyzer_event_transcription_completed(self) -> None:
        """is_analyzer_event returns True for transcription.completed."""
        assert is_analyzer_event("transcription.completed") is True


class TestTranscriptionRequestedEvent:
    """Tests for TranscriptionRequestedEvent dataclass."""

    def test_create_with_all_fields(self) -> None:
        """TranscriptionRequestedEvent can be created with all fields."""
        track = mock_track_info(index=1, track_type="audio", codec="aac")
        event = TranscriptionRequestedEvent(
            file_path=Path("/test/video.mkv"),
            track=track,
            audio_data=b"\x00\x01\x02",
            sample_rate=16000,
            options={"language": "en"},
        )

        assert event.file_path == Path("/test/video.mkv")
        assert event.track == track
        assert event.audio_data == b"\x00\x01\x02"
        assert event.sample_rate == 16000
        assert event.options == {"language": "en"}

    def test_create_with_empty_options(self) -> None:
        """TranscriptionRequestedEvent works with empty options."""
        track = mock_track_info()
        event = TranscriptionRequestedEvent(
            file_path=Path("/test/video.mkv"),
            track=track,
            audio_data=b"",
            sample_rate=44100,
            options={},
        )

        assert event.options == {}

    def test_has_expected_fields(self) -> None:
        """TranscriptionRequestedEvent has all expected fields."""
        event = create_transcription_requested_event()

        assert hasattr(event, "file_path")
        assert hasattr(event, "track")
        assert hasattr(event, "audio_data")
        assert hasattr(event, "sample_rate")
        assert hasattr(event, "options")


class TestTranscriptionCompletedEvent:
    """Tests for TranscriptionCompletedEvent dataclass."""

    def test_create_with_all_fields(self) -> None:
        """TranscriptionCompletedEvent can be created with all fields."""
        result = MagicMock()
        result.detected_language = "eng"
        result.confidence_score = 0.95

        event = TranscriptionCompletedEvent(
            file_path=Path("/test/video.mkv"),
            track_id=42,
            result=result,
        )

        assert event.file_path == Path("/test/video.mkv")
        assert event.track_id == 42
        assert event.result == result
        assert event.result.detected_language == "eng"
        assert event.result.confidence_score == 0.95

    def test_has_expected_fields(self) -> None:
        """TranscriptionCompletedEvent has all expected fields."""
        event = create_transcription_completed_event()

        assert hasattr(event, "file_path")
        assert hasattr(event, "track_id")
        assert hasattr(event, "result")


class TestTranscriptionEventFactories:
    """Tests for SDK factory functions."""

    def test_create_transcription_requested_event_defaults(self) -> None:
        """create_transcription_requested_event creates event with defaults."""
        event = create_transcription_requested_event()

        assert isinstance(event, TranscriptionRequestedEvent)
        assert event.file_path == Path("/test/video.mkv")
        assert event.track is not None
        assert event.track.track_type == "audio"
        assert event.audio_data == b"\x00" * 1000
        assert event.sample_rate == 16000
        assert event.options == {}

    def test_create_transcription_requested_event_custom_values(self) -> None:
        """create_transcription_requested_event accepts custom values."""
        track = mock_track_info(index=5, track_type="audio", codec="flac")
        event = create_transcription_requested_event(
            file_path="/custom/path.mkv",
            track=track,
            audio_data=b"custom_data",
            sample_rate=48000,
            options={"model": "large"},
        )

        assert event.file_path == Path("/custom/path.mkv")
        assert event.track == track
        assert event.audio_data == b"custom_data"
        assert event.sample_rate == 48000
        assert event.options == {"model": "large"}

    def test_create_transcription_completed_event_defaults(self) -> None:
        """create_transcription_completed_event creates event with defaults."""
        event = create_transcription_completed_event()

        assert isinstance(event, TranscriptionCompletedEvent)
        assert event.file_path == Path("/test/video.mkv")
        assert event.track_id == 1
        assert event.result is not None
        assert event.result.detected_language == "eng"
        assert event.result.confidence_score == 0.95

    def test_create_transcription_completed_event_custom_values(self) -> None:
        """create_transcription_completed_event accepts custom values."""
        result = MagicMock()
        result.detected_language = "jpn"

        event = create_transcription_completed_event(
            file_path="/custom/path.mkv",
            track_id=99,
            result=result,
        )

        assert event.file_path == Path("/custom/path.mkv")
        assert event.track_id == 99
        assert event.result.detected_language == "jpn"
