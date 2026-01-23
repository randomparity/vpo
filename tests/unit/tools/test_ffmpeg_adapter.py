"""Tests for tools/ffmpeg_adapter.py - version-aware FFmpeg operations."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.tools.ffmpeg_adapter import (
    FFmpegAdapter,
    FFmpegError,
    get_ffmpeg_adapter,
)
from vpo.tools.models import (
    FFmpegCapabilities,
    FFmpegInfo,
    FFprobeInfo,
    ToolRegistry,
    ToolStatus,
)


class TestFFmpegError:
    """Tests for FFmpegError exceptions."""

    def test_base_error(self) -> None:
        """FFmpegError is catchable exception."""
        with pytest.raises(FFmpegError):
            raise FFmpegError("Test error")


class TestFFmpegAdapter:
    """Tests for FFmpegAdapter class."""

    @pytest.fixture
    def mock_registry(self) -> ToolRegistry:
        """Create mock registry with available FFmpeg."""
        ffmpeg = FFmpegInfo()
        ffmpeg.status = ToolStatus.AVAILABLE
        ffmpeg.path = Path("/usr/bin/ffmpeg")
        ffmpeg.version = "6.0"
        ffmpeg.version_tuple = (6, 0)
        ffmpeg.capabilities = FFmpegCapabilities(
            requires_explicit_pcm_codec=False,
            supports_stats_period=True,
        )

        ffprobe = FFprobeInfo()
        ffprobe.status = ToolStatus.AVAILABLE
        ffprobe.path = Path("/usr/bin/ffprobe")
        ffprobe.version = "6.0"

        return ToolRegistry(ffmpeg=ffmpeg, ffprobe=ffprobe)

    @pytest.fixture
    def adapter(self, mock_registry: ToolRegistry) -> FFmpegAdapter:
        """Create adapter with mock registry."""
        return FFmpegAdapter(registry=mock_registry)

    def test_builder_property(self, adapter: FFmpegAdapter) -> None:
        """Builder property returns configured builder."""
        builder = adapter.builder

        assert builder.ffmpeg_path == Path("/usr/bin/ffmpeg")

    def test_builder_raises_if_unavailable(self) -> None:
        """Builder raises FFmpegError if FFmpeg unavailable."""
        ffmpeg = FFmpegInfo()
        ffmpeg.status = ToolStatus.MISSING
        registry = ToolRegistry(ffmpeg=ffmpeg)
        adapter = FFmpegAdapter(registry=registry)

        with pytest.raises(FFmpegError, match="not available"):
            _ = adapter.builder


class TestExtractAudioStream:
    """Tests for FFmpegAdapter.extract_audio_stream method."""

    @pytest.fixture
    def mock_registry(self) -> ToolRegistry:
        """Create mock registry."""
        ffmpeg = FFmpegInfo()
        ffmpeg.status = ToolStatus.AVAILABLE
        ffmpeg.path = Path("/usr/bin/ffmpeg")
        ffmpeg.version = "6.0"
        ffmpeg.version_tuple = (6, 0)
        ffmpeg.capabilities = FFmpegCapabilities()

        ffprobe = FFprobeInfo()
        ffprobe.status = ToolStatus.AVAILABLE
        ffprobe.path = Path("/usr/bin/ffprobe")

        return ToolRegistry(ffmpeg=ffmpeg, ffprobe=ffprobe)

    def test_successful_extraction(self, mock_registry: ToolRegistry) -> None:
        """Successful extraction returns WAV data."""
        adapter = FFmpegAdapter(registry=mock_registry)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=b"RIFF_wav_data")

            with patch.object(Path, "exists", return_value=True):
                result = adapter.extract_audio_stream(
                    input_path=Path("/test/video.mkv"),
                    track_index=1,
                )

        assert result == b"RIFF_wav_data"

    def test_file_not_found(self, mock_registry: ToolRegistry) -> None:
        """Raises FFmpegError for missing file."""
        adapter = FFmpegAdapter(registry=mock_registry)

        with pytest.raises(FFmpegError, match="File not found"):
            adapter.extract_audio_stream(
                input_path=Path("/nonexistent/file.mkv"),
                track_index=1,
            )

    def test_timeout_error(self, mock_registry: ToolRegistry) -> None:
        """Raises FFmpegError on timeout."""
        adapter = FFmpegAdapter(registry=mock_registry)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["ffmpeg"], timeout=300
            )

            with patch.object(Path, "exists", return_value=True):
                with pytest.raises(FFmpegError, match="timed out"):
                    adapter.extract_audio_stream(
                        input_path=Path("/test/video.mkv"),
                        track_index=1,
                    )

    def test_ffmpeg_failure(self, mock_registry: ToolRegistry) -> None:
        """Raises FFmpegError on command failure."""
        adapter = FFmpegAdapter(registry=mock_registry)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1,
                cmd=["ffmpeg"],
                stderr=b"Invalid track",
            )

            with patch.object(Path, "exists", return_value=True):
                with pytest.raises(FFmpegError, match="Invalid track"):
                    adapter.extract_audio_stream(
                        input_path=Path("/test/video.mkv"),
                        track_index=99,
                    )

    def test_ffmpeg_not_found(self, mock_registry: ToolRegistry) -> None:
        """Raises FFmpegError when FFmpeg not found."""
        adapter = FFmpegAdapter(registry=mock_registry)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            with patch.object(Path, "exists", return_value=True):
                with pytest.raises(FFmpegError, match="not found"):
                    adapter.extract_audio_stream(
                        input_path=Path("/test/video.mkv"),
                        track_index=1,
                    )


class TestGetFileDuration:
    """Tests for FFmpegAdapter.get_file_duration method."""

    @pytest.fixture
    def mock_registry(self) -> ToolRegistry:
        """Create mock registry."""
        ffmpeg = FFmpegInfo()
        ffmpeg.status = ToolStatus.AVAILABLE
        ffmpeg.path = Path("/usr/bin/ffmpeg")
        ffmpeg.capabilities = FFmpegCapabilities()

        ffprobe = FFprobeInfo()
        ffprobe.status = ToolStatus.AVAILABLE
        ffprobe.path = Path("/usr/bin/ffprobe")

        return ToolRegistry(ffmpeg=ffmpeg, ffprobe=ffprobe)

    def test_successful_duration(self, mock_registry: ToolRegistry) -> None:
        """Returns duration from ffprobe."""
        adapter = FFmpegAdapter(registry=mock_registry)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout='{"format": {"duration": "7200.5"}}'
            )

            with patch.object(Path, "exists", return_value=True):
                duration = adapter.get_file_duration(Path("/test/video.mkv"))

        assert duration == 7200.5

    def test_file_not_found(self, mock_registry: ToolRegistry) -> None:
        """Raises FFmpegError for missing file."""
        adapter = FFmpegAdapter(registry=mock_registry)

        with pytest.raises(FFmpegError, match="File not found"):
            adapter.get_file_duration(Path("/nonexistent/file.mkv"))

    def test_ffprobe_unavailable(self) -> None:
        """Raises FFmpegError when ffprobe unavailable."""
        ffmpeg = FFmpegInfo()
        ffmpeg.status = ToolStatus.AVAILABLE
        ffmpeg.path = Path("/usr/bin/ffmpeg")
        ffmpeg.capabilities = FFmpegCapabilities()

        ffprobe = FFprobeInfo()
        ffprobe.status = ToolStatus.MISSING

        registry = ToolRegistry(ffmpeg=ffmpeg, ffprobe=ffprobe)
        adapter = FFmpegAdapter(registry=registry)

        with patch.object(Path, "exists", return_value=True):
            with pytest.raises(FFmpegError, match="not available"):
                adapter.get_file_duration(Path("/test/video.mkv"))


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_get_ffmpeg_adapter_caches(self) -> None:
        """get_ffmpeg_adapter returns cached instance."""
        import vpo.tools.ffmpeg_adapter as adapter_module

        # Clear any existing cache
        adapter_module._adapter_cache = None

        with patch("vpo.tools.cache.get_tool_registry") as mock_get:
            ffmpeg = FFmpegInfo()
            ffmpeg.status = ToolStatus.AVAILABLE
            ffmpeg.path = Path("/usr/bin/ffmpeg")
            ffmpeg.capabilities = FFmpegCapabilities()
            mock_get.return_value = ToolRegistry(ffmpeg=ffmpeg)

            adapter1 = get_ffmpeg_adapter()
            adapter2 = get_ffmpeg_adapter()

            assert adapter1 is adapter2
            # Only called once due to caching
            assert mock_get.call_count == 1

        # Clean up
        adapter_module._adapter_cache = None
