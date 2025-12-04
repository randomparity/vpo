"""Unit tests for plugin_sdk audio module.

Tests verify the SDK module's public interface for audio extraction utilities.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from video_policy_orchestrator.plugin_sdk.audio import (
    AudioExtractionError,
    extract_audio_stream,
    get_file_duration,
    is_ffmpeg_available,
)


class TestExtractAudioStream:
    """Tests for extract_audio_stream function."""

    @patch("video_policy_orchestrator.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_successful_extraction(self, mock_get_adapter: MagicMock) -> None:
        """Test successful audio extraction."""
        mock_adapter = MagicMock()
        mock_adapter.extract_audio_stream.return_value = b"fake_wav_data"
        mock_get_adapter.return_value = mock_adapter

        result = extract_audio_stream(Path("/test/movie.mkv"), track_index=1)

        assert result == b"fake_wav_data"
        mock_adapter.extract_audio_stream.assert_called_once()

    @patch("video_policy_orchestrator.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_default_parameters(self, mock_get_adapter: MagicMock) -> None:
        """Test extraction with default parameters."""
        mock_adapter = MagicMock()
        mock_adapter.extract_audio_stream.return_value = b"wav_data"
        mock_get_adapter.return_value = mock_adapter

        extract_audio_stream(Path("/test/movie.mkv"), track_index=0)

        call_kwargs = mock_adapter.extract_audio_stream.call_args[1]
        assert call_kwargs["sample_rate"] == 16000
        assert call_kwargs["sample_duration"] == 60
        assert call_kwargs["start_offset"] == 0.0

    @patch("video_policy_orchestrator.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_custom_parameters(self, mock_get_adapter: MagicMock) -> None:
        """Test extraction with custom parameters."""
        mock_adapter = MagicMock()
        mock_adapter.extract_audio_stream.return_value = b"wav_data"
        mock_get_adapter.return_value = mock_adapter

        extract_audio_stream(
            Path("/test/movie.mkv"),
            track_index=0,
            sample_duration=30,
            sample_rate=22050,
            start_offset=100.0,
        )

        call_kwargs = mock_adapter.extract_audio_stream.call_args[1]
        assert call_kwargs["sample_duration"] == 30
        assert call_kwargs["sample_rate"] == 22050
        assert call_kwargs["start_offset"] == 100.0

    @patch("video_policy_orchestrator.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_zero_duration_extracts_full_track(
        self, mock_get_adapter: MagicMock
    ) -> None:
        """Test that sample_duration=0 extracts full track."""
        mock_adapter = MagicMock()
        mock_adapter.extract_audio_stream.return_value = b"wav_data"
        mock_get_adapter.return_value = mock_adapter

        extract_audio_stream(
            Path("/test/movie.mkv"),
            track_index=0,
            sample_duration=0,
        )

        call_kwargs = mock_adapter.extract_audio_stream.call_args[1]
        assert call_kwargs["sample_duration"] is None

    @patch("video_policy_orchestrator.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_ffmpeg_error_wrapped(self, mock_get_adapter: MagicMock) -> None:
        """Test that FFmpegError is wrapped in AudioExtractionError."""
        from video_policy_orchestrator.tools.ffmpeg_adapter import FFmpegError

        mock_adapter = MagicMock()
        mock_adapter.extract_audio_stream.side_effect = FFmpegError("Test error")
        mock_get_adapter.return_value = mock_adapter

        with pytest.raises(AudioExtractionError, match="Test error"):
            extract_audio_stream(Path("/test/movie.mkv"), track_index=0)


class TestIsFfmpegAvailable:
    """Tests for is_ffmpeg_available function."""

    @patch("video_policy_orchestrator.tools.cache.get_tool_registry")
    def test_returns_true_when_available(self, mock_get_registry: MagicMock) -> None:
        """Test detection of available ffmpeg."""
        mock_registry = MagicMock()
        mock_registry.ffmpeg.is_available.return_value = True
        mock_get_registry.return_value = mock_registry

        assert is_ffmpeg_available() is True

    @patch("video_policy_orchestrator.tools.cache.get_tool_registry")
    def test_returns_false_when_unavailable(self, mock_get_registry: MagicMock) -> None:
        """Test detection when ffmpeg is not available."""
        mock_registry = MagicMock()
        mock_registry.ffmpeg.is_available.return_value = False
        mock_get_registry.return_value = mock_registry

        assert is_ffmpeg_available() is False

    @patch("video_policy_orchestrator.tools.cache.get_tool_registry")
    def test_exception_returns_false(self, mock_get_registry: MagicMock) -> None:
        """Test that exceptions result in False."""
        mock_get_registry.side_effect = Exception("Registry error")

        assert is_ffmpeg_available() is False


class TestGetFileDuration:
    """Tests for get_file_duration function."""

    @patch("video_policy_orchestrator.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_successful_extraction(self, mock_get_adapter: MagicMock) -> None:
        """Test successful duration extraction."""
        mock_adapter = MagicMock()
        mock_adapter.get_file_duration.return_value = 7200.5
        mock_get_adapter.return_value = mock_adapter

        duration = get_file_duration(Path("/test/movie.mkv"))

        assert duration == 7200.5
        mock_adapter.get_file_duration.assert_called_once_with(Path("/test/movie.mkv"))

    @patch("video_policy_orchestrator.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_error_wrapped(self, mock_get_adapter: MagicMock) -> None:
        """Test that FFmpegError is wrapped in AudioExtractionError."""
        from video_policy_orchestrator.tools.ffmpeg_adapter import FFmpegError

        mock_adapter = MagicMock()
        mock_adapter.get_file_duration.side_effect = FFmpegError("Cannot get duration")
        mock_get_adapter.return_value = mock_adapter

        with pytest.raises(AudioExtractionError, match="Cannot get duration"):
            get_file_duration(Path("/test/movie.mkv"))


class TestAudioExtractionError:
    """Tests for AudioExtractionError exception."""

    def test_is_exception(self) -> None:
        """AudioExtractionError is an Exception."""
        assert issubclass(AudioExtractionError, Exception)

    def test_inherits_from_transcription_error(self) -> None:
        """AudioExtractionError inherits from TranscriptionError."""
        from video_policy_orchestrator.transcription.interface import TranscriptionError

        assert issubclass(AudioExtractionError, TranscriptionError)

    def test_message_preserved(self) -> None:
        """Error message is preserved."""
        error = AudioExtractionError("ffmpeg failed")
        assert str(error) == "ffmpeg failed"

    def test_can_be_raised_and_caught(self) -> None:
        """Can raise and catch AudioExtractionError."""
        with pytest.raises(AudioExtractionError):
            raise AudioExtractionError("test error")


class TestSdkImports:
    """Tests to verify SDK imports work correctly."""

    def test_import_from_plugin_sdk(self) -> None:
        """Verify utilities can be imported from plugin_sdk."""
        from video_policy_orchestrator.plugin_sdk import (
            AudioExtractionError,
            extract_audio_stream,
            get_file_duration,
            is_ffmpeg_available,
        )

        # Just verify they're callable/types
        assert callable(extract_audio_stream)
        assert callable(get_file_duration)
        assert callable(is_ffmpeg_available)
        assert issubclass(AudioExtractionError, Exception)

    def test_import_from_audio_module(self) -> None:
        """Verify utilities can be imported from audio submodule."""
        from video_policy_orchestrator.plugin_sdk.audio import (
            AudioExtractionError,
            extract_audio_stream,
            get_file_duration,
            is_ffmpeg_available,
        )

        assert callable(extract_audio_stream)
        assert callable(get_file_duration)
        assert callable(is_ffmpeg_available)
        assert issubclass(AudioExtractionError, Exception)
