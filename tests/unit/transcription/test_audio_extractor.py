"""Unit tests for audio_extractor module.

The audio_extractor module now delegates to FFmpegAdapter for actual
extraction operations. These tests verify the public API behavior by
mocking the adapter layer.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.transcription.audio_extractor import (
    AudioExtractionError,
    extract_audio_stream,
    get_file_duration,
    is_ffmpeg_available,
)


class TestExtractAudioStream:
    """Tests for extract_audio_stream function."""

    @patch("vpo.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_successful_extraction(self, mock_get_adapter: MagicMock) -> None:
        """Test successful audio extraction."""
        mock_adapter = MagicMock()
        mock_adapter.extract_audio_stream.return_value = b"fake_wav_data"
        mock_get_adapter.return_value = mock_adapter

        result = extract_audio_stream(
            Path("/test/movie.mkv"),
            track_index=1,
        )

        assert result == b"fake_wav_data"
        mock_adapter.extract_audio_stream.assert_called_once_with(
            input_path=Path("/test/movie.mkv"),
            track_index=1,
            sample_rate=16000,
            sample_duration=60,
            start_offset=0.0,
        )

    @patch("vpo.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_custom_sample_duration(self, mock_get_adapter: MagicMock) -> None:
        """Test extraction with custom sample duration."""
        mock_adapter = MagicMock()
        mock_adapter.extract_audio_stream.return_value = b"wav_data"
        mock_get_adapter.return_value = mock_adapter

        extract_audio_stream(
            Path("/test/movie.mkv"),
            track_index=0,
            sample_duration=30,
        )

        mock_adapter.extract_audio_stream.assert_called_once()
        call_kwargs = mock_adapter.extract_audio_stream.call_args[1]
        assert call_kwargs["sample_duration"] == 30

    @patch("vpo.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_full_track_extraction(self, mock_get_adapter: MagicMock) -> None:
        """Test extraction of full track (sample_duration=0)."""
        mock_adapter = MagicMock()
        mock_adapter.extract_audio_stream.return_value = b"wav_data"
        mock_get_adapter.return_value = mock_adapter

        extract_audio_stream(
            Path("/test/movie.mkv"),
            track_index=0,
            sample_duration=0,
        )

        call_kwargs = mock_adapter.extract_audio_stream.call_args[1]
        # sample_duration=0 means full track, passed as None to adapter
        assert call_kwargs["sample_duration"] is None

    @patch("vpo.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_ffmpeg_error_wrapped(self, mock_get_adapter: MagicMock) -> None:
        """Test that FFmpegError is wrapped in AudioExtractionError."""
        from vpo.tools.ffmpeg_adapter import FFmpegError

        mock_adapter = MagicMock()
        mock_adapter.extract_audio_stream.side_effect = FFmpegError("Test error")
        mock_get_adapter.return_value = mock_adapter

        with pytest.raises(AudioExtractionError, match="Test error"):
            extract_audio_stream(Path("/test/movie.mkv"), track_index=0)

    @patch("vpo.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_file_not_found(self, mock_get_adapter: MagicMock) -> None:
        """Test error when file doesn't exist."""
        from vpo.tools.ffmpeg_adapter import FFmpegError

        mock_adapter = MagicMock()
        mock_adapter.extract_audio_stream.side_effect = FFmpegError(
            "File not found: /nonexistent/file.mkv"
        )
        mock_get_adapter.return_value = mock_adapter

        with pytest.raises(AudioExtractionError, match="File not found"):
            extract_audio_stream(Path("/nonexistent/file.mkv"), track_index=0)

    @patch("vpo.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_ffmpeg_timeout(self, mock_get_adapter: MagicMock) -> None:
        """Test handling of ffmpeg timeout."""
        from vpo.tools.ffmpeg_adapter import FFmpegError

        mock_adapter = MagicMock()
        mock_adapter.extract_audio_stream.side_effect = FFmpegError(
            "FFmpeg timed out after 300s"
        )
        mock_get_adapter.return_value = mock_adapter

        with pytest.raises(AudioExtractionError, match="timed out"):
            extract_audio_stream(Path("/test/movie.mkv"), track_index=0)

    @patch("vpo.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_ffmpeg_not_found(self, mock_get_adapter: MagicMock) -> None:
        """Test handling of ffmpeg not being installed."""
        from vpo.tools.ffmpeg_adapter import FFmpegError

        mock_adapter = MagicMock()
        mock_adapter.extract_audio_stream.side_effect = FFmpegError("FFmpeg not found")
        mock_get_adapter.return_value = mock_adapter

        with pytest.raises(AudioExtractionError, match="not found"):
            extract_audio_stream(Path("/test/movie.mkv"), track_index=0)


class TestIsFfmpegAvailable:
    """Tests for is_ffmpeg_available function."""

    @patch("vpo.tools.cache.get_tool_registry")
    def test_ffmpeg_available(self, mock_get_registry: MagicMock) -> None:
        """Test detection of available ffmpeg."""
        mock_registry = MagicMock()
        mock_registry.ffmpeg.is_available.return_value = True
        mock_get_registry.return_value = mock_registry

        result = is_ffmpeg_available()

        assert result is True

    @patch("vpo.tools.cache.get_tool_registry")
    def test_ffmpeg_not_available(self, mock_get_registry: MagicMock) -> None:
        """Test detection when ffmpeg is not available."""
        mock_registry = MagicMock()
        mock_registry.ffmpeg.is_available.return_value = False
        mock_get_registry.return_value = mock_registry

        result = is_ffmpeg_available()

        assert result is False

    @patch("vpo.tools.cache.get_tool_registry")
    def test_exception_returns_false(self, mock_get_registry: MagicMock) -> None:
        """Test that exceptions result in False."""
        mock_get_registry.side_effect = Exception("Registry error")

        result = is_ffmpeg_available()

        assert result is False


class TestExtractAudioStreamOffset:
    """Tests for extract_audio_stream start_offset parameter."""

    @patch("vpo.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_with_start_offset(self, mock_get_adapter: MagicMock) -> None:
        """Test extraction with start_offset."""
        mock_adapter = MagicMock()
        mock_adapter.extract_audio_stream.return_value = b"wav_data"
        mock_get_adapter.return_value = mock_adapter

        extract_audio_stream(
            Path("/test/movie.mkv"),
            track_index=1,
            start_offset=300.0,
        )

        call_kwargs = mock_adapter.extract_audio_stream.call_args[1]
        assert call_kwargs["start_offset"] == 300.0

    @patch("vpo.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_without_start_offset(self, mock_get_adapter: MagicMock) -> None:
        """Test extraction without start_offset."""
        mock_adapter = MagicMock()
        mock_adapter.extract_audio_stream.return_value = b"wav_data"
        mock_get_adapter.return_value = mock_adapter

        extract_audio_stream(
            Path("/test/movie.mkv"),
            track_index=1,
            start_offset=0.0,
        )

        call_kwargs = mock_adapter.extract_audio_stream.call_args[1]
        assert call_kwargs["start_offset"] == 0.0

    @patch("vpo.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_start_offset_with_duration(self, mock_get_adapter: MagicMock) -> None:
        """Test extraction with both start_offset and sample_duration."""
        mock_adapter = MagicMock()
        mock_adapter.extract_audio_stream.return_value = b"wav_data"
        mock_get_adapter.return_value = mock_adapter

        extract_audio_stream(
            Path("/test/movie.mkv"),
            track_index=1,
            start_offset=600.0,
            sample_duration=30,
        )

        call_kwargs = mock_adapter.extract_audio_stream.call_args[1]
        assert call_kwargs["start_offset"] == 600.0
        assert call_kwargs["sample_duration"] == 30


class TestGetFileDuration:
    """Tests for get_file_duration function."""

    @patch("vpo.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_successful_duration_extraction(self, mock_get_adapter: MagicMock) -> None:
        """Test successful duration extraction."""
        mock_adapter = MagicMock()
        mock_adapter.get_file_duration.return_value = 7200.5
        mock_get_adapter.return_value = mock_adapter

        duration = get_file_duration(Path("/test/movie.mkv"))

        assert duration == 7200.5
        mock_adapter.get_file_duration.assert_called_once_with(Path("/test/movie.mkv"))

    @patch("vpo.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_file_not_found(self, mock_get_adapter: MagicMock) -> None:
        """Test error when file doesn't exist."""
        from vpo.tools.ffmpeg_adapter import FFmpegError

        mock_adapter = MagicMock()
        mock_adapter.get_file_duration.side_effect = FFmpegError(
            "File not found: /nonexistent/file.mkv"
        )
        mock_get_adapter.return_value = mock_adapter

        with pytest.raises(AudioExtractionError, match="File not found"):
            get_file_duration(Path("/nonexistent/file.mkv"))

    @patch("vpo.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_no_duration_in_output(self, mock_get_adapter: MagicMock) -> None:
        """Test error when duration is missing from output."""
        from vpo.tools.ffmpeg_adapter import FFmpegError

        mock_adapter = MagicMock()
        mock_adapter.get_file_duration.side_effect = FFmpegError(
            "Could not determine duration"
        )
        mock_get_adapter.return_value = mock_adapter

        with pytest.raises(AudioExtractionError, match="Could not determine"):
            get_file_duration(Path("/test/movie.mkv"))

    @patch("vpo.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_ffprobe_error(self, mock_get_adapter: MagicMock) -> None:
        """Test handling of ffprobe errors."""
        from vpo.tools.ffmpeg_adapter import FFmpegError

        mock_adapter = MagicMock()
        mock_adapter.get_file_duration.side_effect = FFmpegError(
            "ffprobe failed for /test/movie.mkv: Invalid file"
        )
        mock_get_adapter.return_value = mock_adapter

        with pytest.raises(AudioExtractionError, match="ffprobe failed"):
            get_file_duration(Path("/test/movie.mkv"))

    @patch("vpo.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_ffprobe_timeout(self, mock_get_adapter: MagicMock) -> None:
        """Test handling of ffprobe timeout."""
        from vpo.tools.ffmpeg_adapter import FFmpegError

        mock_adapter = MagicMock()
        mock_adapter.get_file_duration.side_effect = FFmpegError("ffprobe timed out")
        mock_get_adapter.return_value = mock_adapter

        with pytest.raises(AudioExtractionError, match="timed out"):
            get_file_duration(Path("/test/movie.mkv"))

    @patch("vpo.tools.ffmpeg_adapter.get_ffmpeg_adapter")
    def test_ffprobe_not_found(self, mock_get_adapter: MagicMock) -> None:
        """Test handling of ffprobe not being installed."""
        from vpo.tools.ffmpeg_adapter import FFmpegError

        mock_adapter = MagicMock()
        mock_adapter.get_file_duration.side_effect = FFmpegError("ffprobe not found")
        mock_get_adapter.return_value = mock_adapter

        with pytest.raises(AudioExtractionError, match="not found"):
            get_file_duration(Path("/test/movie.mkv"))
