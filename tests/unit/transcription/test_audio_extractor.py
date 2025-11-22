"""Unit tests for audio_extractor module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from video_policy_orchestrator.transcription.audio_extractor import (
    AudioExtractionError,
    extract_audio_stream,
    is_ffmpeg_available,
)


class TestExtractAudioStream:
    """Tests for extract_audio_stream function."""

    @patch("video_policy_orchestrator.transcription.audio_extractor.subprocess.run")
    def test_successful_extraction(self, mock_run: MagicMock):
        """Test successful audio extraction."""
        mock_run.return_value = MagicMock(stdout=b"fake_wav_data")
        file_path = Path("/test/movie.mkv")

        # Mock file existence
        with patch.object(Path, "exists", return_value=True):
            result = extract_audio_stream(file_path, track_index=1)

        assert result == b"fake_wav_data"
        mock_run.assert_called_once()

        # Verify ffmpeg command structure
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert cmd[0] == "ffmpeg"
        assert "-map" in cmd
        assert "0:1" in cmd
        assert "-ac" in cmd
        assert "1" in cmd  # mono
        assert "-ar" in cmd
        assert "16000" in cmd  # sample rate
        assert "-f" in cmd
        assert "wav" in cmd
        assert "pipe:1" in cmd

    @patch("video_policy_orchestrator.transcription.audio_extractor.subprocess.run")
    def test_custom_sample_duration(self, mock_run: MagicMock):
        """Test extraction with custom sample duration."""
        mock_run.return_value = MagicMock(stdout=b"wav_data")
        file_path = Path("/test/movie.mkv")

        with patch.object(Path, "exists", return_value=True):
            extract_audio_stream(file_path, track_index=0, sample_duration=30)

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "-t" in cmd
        assert "30" in cmd

    @patch("video_policy_orchestrator.transcription.audio_extractor.subprocess.run")
    def test_full_track_extraction(self, mock_run: MagicMock):
        """Test extraction of full track (sample_duration=0)."""
        mock_run.return_value = MagicMock(stdout=b"wav_data")
        file_path = Path("/test/movie.mkv")

        with patch.object(Path, "exists", return_value=True):
            extract_audio_stream(file_path, track_index=0, sample_duration=0)

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        # -t should not be present when sample_duration=0
        assert "-t" not in cmd

    def test_file_not_found(self):
        """Test error when file doesn't exist."""
        file_path = Path("/nonexistent/file.mkv")

        with pytest.raises(AudioExtractionError, match="File not found"):
            extract_audio_stream(file_path, track_index=0)

    @patch("video_policy_orchestrator.transcription.audio_extractor.subprocess.run")
    def test_ffmpeg_error(self, mock_run: MagicMock):
        """Test handling of ffmpeg errors."""
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["ffmpeg"], stderr=b"Invalid track index"
        )
        file_path = Path("/test/movie.mkv")

        with patch.object(Path, "exists", return_value=True):
            with pytest.raises(AudioExtractionError, match="ffmpeg failed"):
                extract_audio_stream(file_path, track_index=99)

    @patch("video_policy_orchestrator.transcription.audio_extractor.subprocess.run")
    def test_ffmpeg_timeout(self, mock_run: MagicMock):
        """Test handling of ffmpeg timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["ffmpeg"], timeout=300)
        file_path = Path("/test/movie.mkv")

        with patch.object(Path, "exists", return_value=True):
            with pytest.raises(AudioExtractionError, match="timed out"):
                extract_audio_stream(file_path, track_index=0)

    @patch("video_policy_orchestrator.transcription.audio_extractor.subprocess.run")
    def test_ffmpeg_not_found(self, mock_run: MagicMock):
        """Test handling of ffmpeg not being installed."""
        mock_run.side_effect = FileNotFoundError()
        file_path = Path("/test/movie.mkv")

        with patch.object(Path, "exists", return_value=True):
            with pytest.raises(AudioExtractionError, match="ffmpeg not found"):
                extract_audio_stream(file_path, track_index=0)


class TestIsFfmpegAvailable:
    """Tests for is_ffmpeg_available function."""

    @patch("video_policy_orchestrator.transcription.audio_extractor.subprocess.run")
    def test_ffmpeg_available(self, mock_run: MagicMock):
        """Test detection of available ffmpeg."""
        mock_run.return_value = MagicMock(returncode=0)

        result = is_ffmpeg_available()

        assert result is True
        mock_run.assert_called_once()

    @patch("video_policy_orchestrator.transcription.audio_extractor.subprocess.run")
    def test_ffmpeg_not_available(self, mock_run: MagicMock):
        """Test detection when ffmpeg is not available."""
        mock_run.side_effect = FileNotFoundError()

        result = is_ffmpeg_available()

        assert result is False

    @patch("video_policy_orchestrator.transcription.audio_extractor.subprocess.run")
    def test_ffmpeg_timeout(self, mock_run: MagicMock):
        """Test handling of timeout when checking ffmpeg."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["ffmpeg"], timeout=10)

        result = is_ffmpeg_available()

        assert result is False
