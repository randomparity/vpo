"""Unit tests for audio_extractor module."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from video_policy_orchestrator.transcription.audio_extractor import (
    AudioExtractionError,
    extract_audio_stream,
    get_file_duration,
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


class TestExtractAudioStreamOffset:
    """Tests for extract_audio_stream start_offset parameter."""

    @patch("video_policy_orchestrator.transcription.audio_extractor.subprocess.run")
    def test_with_start_offset(self, mock_run: MagicMock):
        """Test extraction with start_offset includes -ss flag."""
        mock_run.return_value = MagicMock(stdout=b"wav_data")
        file_path = Path("/test/movie.mkv")

        with patch.object(Path, "exists", return_value=True):
            extract_audio_stream(file_path, track_index=1, start_offset=300.0)

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "-ss" in cmd
        ss_idx = cmd.index("-ss")
        assert cmd[ss_idx + 1] == "300.0"
        # -ss should come before -i for input seeking
        i_idx = cmd.index("-i")
        assert ss_idx < i_idx

    @patch("video_policy_orchestrator.transcription.audio_extractor.subprocess.run")
    def test_without_start_offset(self, mock_run: MagicMock):
        """Test extraction without start_offset omits -ss flag."""
        mock_run.return_value = MagicMock(stdout=b"wav_data")
        file_path = Path("/test/movie.mkv")

        with patch.object(Path, "exists", return_value=True):
            extract_audio_stream(file_path, track_index=1, start_offset=0.0)

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "-ss" not in cmd

    @patch("video_policy_orchestrator.transcription.audio_extractor.subprocess.run")
    def test_start_offset_with_duration(self, mock_run: MagicMock):
        """Test extraction with both start_offset and sample_duration."""
        mock_run.return_value = MagicMock(stdout=b"wav_data")
        file_path = Path("/test/movie.mkv")

        with patch.object(Path, "exists", return_value=True):
            extract_audio_stream(
                file_path,
                track_index=1,
                start_offset=600.0,
                sample_duration=30,
            )

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "-ss" in cmd
        assert "-t" in cmd
        assert "30" in cmd


class TestGetFileDuration:
    """Tests for get_file_duration function."""

    @patch("video_policy_orchestrator.transcription.audio_extractor.subprocess.run")
    def test_successful_duration_extraction(self, mock_run: MagicMock):
        """Test successful duration extraction."""
        mock_output = json.dumps({"format": {"duration": "7200.5"}})
        mock_run.return_value = MagicMock(stdout=mock_output)
        file_path = Path("/test/movie.mkv")

        with patch.object(Path, "exists", return_value=True):
            duration = get_file_duration(file_path)

        assert duration == 7200.5
        mock_run.assert_called_once()

        # Verify ffprobe command structure
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert cmd[0] == "ffprobe"
        assert "-show_entries" in cmd
        assert "format=duration" in cmd

    def test_file_not_found(self):
        """Test error when file doesn't exist."""
        file_path = Path("/nonexistent/file.mkv")

        with pytest.raises(AudioExtractionError, match="File not found"):
            get_file_duration(file_path)

    @patch("video_policy_orchestrator.transcription.audio_extractor.subprocess.run")
    def test_no_duration_in_output(self, mock_run: MagicMock):
        """Test error when duration is missing from output."""
        mock_output = json.dumps({"format": {}})
        mock_run.return_value = MagicMock(stdout=mock_output)
        file_path = Path("/test/movie.mkv")

        with patch.object(Path, "exists", return_value=True):
            with pytest.raises(AudioExtractionError, match="Could not determine"):
                get_file_duration(file_path)

    @patch("video_policy_orchestrator.transcription.audio_extractor.subprocess.run")
    def test_invalid_json_output(self, mock_run: MagicMock):
        """Test error when ffprobe returns invalid JSON."""
        mock_run.return_value = MagicMock(stdout="not valid json")
        file_path = Path("/test/movie.mkv")

        with patch.object(Path, "exists", return_value=True):
            with pytest.raises(AudioExtractionError, match="Could not parse"):
                get_file_duration(file_path)

    @patch("video_policy_orchestrator.transcription.audio_extractor.subprocess.run")
    def test_ffprobe_error(self, mock_run: MagicMock):
        """Test handling of ffprobe errors."""
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["ffprobe"], stderr="Invalid file"
        )
        file_path = Path("/test/movie.mkv")

        with patch.object(Path, "exists", return_value=True):
            with pytest.raises(AudioExtractionError, match="ffprobe failed"):
                get_file_duration(file_path)

    @patch("video_policy_orchestrator.transcription.audio_extractor.subprocess.run")
    def test_ffprobe_timeout(self, mock_run: MagicMock):
        """Test handling of ffprobe timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["ffprobe"], timeout=30)
        file_path = Path("/test/movie.mkv")

        with patch.object(Path, "exists", return_value=True):
            with pytest.raises(AudioExtractionError, match="timed out"):
                get_file_duration(file_path)

    @patch("video_policy_orchestrator.transcription.audio_extractor.subprocess.run")
    def test_ffprobe_not_found(self, mock_run: MagicMock):
        """Test handling of ffprobe not being installed."""
        mock_run.side_effect = FileNotFoundError()
        file_path = Path("/test/movie.mkv")

        with patch.object(Path, "exists", return_value=True):
            with pytest.raises(AudioExtractionError, match="ffprobe not found"):
                get_file_duration(file_path)
