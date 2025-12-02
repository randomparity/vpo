"""Tests for tools/ffmpeg_builder.py - version-aware command building."""

from pathlib import Path

import pytest

from video_policy_orchestrator.tools.ffmpeg_builder import FFmpegCommandBuilder
from video_policy_orchestrator.tools.models import FFmpegCapabilities


class TestFFmpegCommandBuilder:
    """Tests for FFmpegCommandBuilder class."""

    @pytest.fixture
    def default_caps(self) -> FFmpegCapabilities:
        """Create default capabilities."""
        return FFmpegCapabilities()

    @pytest.fixture
    def modern_caps(self) -> FFmpegCapabilities:
        """Create capabilities for modern FFmpeg (5.1+)."""
        return FFmpegCapabilities(
            supports_stats_period=True,
            supports_fps_mode=True,
            requires_explicit_pcm_codec=False,
        )

    @pytest.fixture
    def legacy_caps(self) -> FFmpegCapabilities:
        """Create capabilities for legacy FFmpeg (pre-4.3)."""
        return FFmpegCapabilities(
            supports_stats_period=False,
            supports_fps_mode=False,
            requires_explicit_pcm_codec=True,
        )

    @pytest.fixture
    def builder(self, default_caps: FFmpegCapabilities) -> FFmpegCommandBuilder:
        """Create builder with default capabilities."""
        return FFmpegCommandBuilder(
            capabilities=default_caps,
            ffmpeg_path=Path("/usr/bin/ffmpeg"),
        )


class TestBaseCommand:
    """Tests for base_command method."""

    def test_includes_ffmpeg_path(self) -> None:
        """Base command starts with ffmpeg path."""
        caps = FFmpegCapabilities()
        builder = FFmpegCommandBuilder(caps, Path("/custom/ffmpeg"))

        cmd = builder.base_command()

        assert cmd[0] == "/custom/ffmpeg"

    def test_includes_hide_banner(self) -> None:
        """Base command includes -hide_banner."""
        caps = FFmpegCapabilities()
        builder = FFmpegCommandBuilder(caps, Path("/usr/bin/ffmpeg"))

        cmd = builder.base_command()

        assert "-hide_banner" in cmd

    def test_includes_overwrite(self) -> None:
        """Base command includes -y for overwrite."""
        caps = FFmpegCapabilities()
        builder = FFmpegCommandBuilder(caps, Path("/usr/bin/ffmpeg"))

        cmd = builder.base_command()

        assert "-y" in cmd


class TestWithLoglevel:
    """Tests for with_loglevel method."""

    def test_adds_loglevel(self) -> None:
        """Adds -loglevel flag."""
        caps = FFmpegCapabilities()
        builder = FFmpegCommandBuilder(caps, Path("/usr/bin/ffmpeg"))

        cmd = builder.with_loglevel([], "error")

        assert "-loglevel" in cmd
        assert "error" in cmd

    def test_custom_level(self) -> None:
        """Supports custom log levels."""
        caps = FFmpegCapabilities()
        builder = FFmpegCommandBuilder(caps, Path("/usr/bin/ffmpeg"))

        cmd = builder.with_loglevel([], "warning")

        assert "warning" in cmd


class TestWithProgress:
    """Tests for with_progress method."""

    def test_modern_ffmpeg_uses_stats_period(self) -> None:
        """Modern FFmpeg uses -stats_period."""
        caps = FFmpegCapabilities(supports_stats_period=True)
        builder = FFmpegCommandBuilder(caps, Path("/usr/bin/ffmpeg"))

        cmd = builder.with_progress([], period_seconds=2)

        assert "-stats_period" in cmd
        assert "2" in cmd
        assert "-stats" not in cmd

    def test_legacy_ffmpeg_uses_stats(self) -> None:
        """Legacy FFmpeg uses -stats fallback."""
        caps = FFmpegCapabilities(supports_stats_period=False)
        builder = FFmpegCommandBuilder(caps, Path("/usr/bin/ffmpeg"))

        cmd = builder.with_progress([])

        assert "-stats" in cmd
        assert "-stats_period" not in cmd

    def test_custom_period(self) -> None:
        """Supports custom period."""
        caps = FFmpegCapabilities(supports_stats_period=True)
        builder = FFmpegCommandBuilder(caps, Path("/usr/bin/ffmpeg"))

        cmd = builder.with_progress([], period_seconds=5)

        assert "5" in cmd


class TestWavOutputArgs:
    """Tests for wav_output_args method."""

    def test_with_explicit_codec(self) -> None:
        """Includes -acodec when required."""
        caps = FFmpegCapabilities(requires_explicit_pcm_codec=True)
        builder = FFmpegCommandBuilder(caps, Path("/usr/bin/ffmpeg"))

        args = builder.wav_output_args("output.wav")

        assert "-acodec" in args
        assert "pcm_s16le" in args
        assert "-f" in args
        assert "wav" in args
        assert "output.wav" in args

    def test_without_explicit_codec(self) -> None:
        """Omits -acodec when not required."""
        caps = FFmpegCapabilities(requires_explicit_pcm_codec=False)
        builder = FFmpegCommandBuilder(caps, Path("/usr/bin/ffmpeg"))

        args = builder.wav_output_args("output.wav")

        assert "-acodec" not in args
        assert "pcm_s16le" not in args
        assert "-f" in args
        assert "wav" in args

    def test_pipe_output(self) -> None:
        """Supports pipe output."""
        caps = FFmpegCapabilities()
        builder = FFmpegCommandBuilder(caps, Path("/usr/bin/ffmpeg"))

        args = builder.wav_output_args("pipe:1")

        assert "pipe:1" in args


class TestFpsArgs:
    """Tests for fps_args method."""

    def test_modern_ffmpeg_uses_fps_mode(self) -> None:
        """Modern FFmpeg uses -fps_mode."""
        caps = FFmpegCapabilities(supports_fps_mode=True)
        builder = FFmpegCommandBuilder(caps, Path("/usr/bin/ffmpeg"))

        args = builder.fps_args("vfr")

        assert "-fps_mode" in args
        assert "vfr" in args
        assert "-vsync" not in args

    def test_legacy_ffmpeg_uses_vsync(self) -> None:
        """Legacy FFmpeg uses -vsync."""
        caps = FFmpegCapabilities(supports_fps_mode=False)
        builder = FFmpegCommandBuilder(caps, Path("/usr/bin/ffmpeg"))

        args = builder.fps_args("vfr")

        assert "-vsync" in args
        assert "vfr" in args
        assert "-fps_mode" not in args

    def test_cfr_mode(self) -> None:
        """Supports cfr mode."""
        caps = FFmpegCapabilities(supports_fps_mode=True)
        builder = FFmpegCommandBuilder(caps, Path("/usr/bin/ffmpeg"))

        args = builder.fps_args("cfr")

        assert "cfr" in args


class TestAudioExtractArgs:
    """Tests for audio_extract_args method."""

    def test_basic_extraction(self) -> None:
        """Builds basic audio extraction command."""
        caps = FFmpegCapabilities()
        builder = FFmpegCommandBuilder(caps, Path("/usr/bin/ffmpeg"))

        cmd = builder.audio_extract_args(
            input_path=Path("/test/video.mkv"),
            track_index=1,
        )

        assert cmd[0] == "/usr/bin/ffmpeg"
        assert "-i" in cmd
        assert "/test/video.mkv" in cmd
        assert "-map" in cmd
        assert "0:1" in cmd
        assert "-ac" in cmd
        assert "1" in cmd
        assert "-ar" in cmd
        assert "16000" in cmd
        assert "pipe:1" in cmd

    def test_with_start_offset(self) -> None:
        """Includes -ss before input."""
        caps = FFmpegCapabilities()
        builder = FFmpegCommandBuilder(caps, Path("/usr/bin/ffmpeg"))

        cmd = builder.audio_extract_args(
            input_path=Path("/test/video.mkv"),
            track_index=1,
            start_offset=300.0,
        )

        assert "-ss" in cmd
        ss_idx = cmd.index("-ss")
        i_idx = cmd.index("-i")
        # -ss should come before -i
        assert ss_idx < i_idx

    def test_with_duration(self) -> None:
        """Includes -t for duration limit."""
        caps = FFmpegCapabilities()
        builder = FFmpegCommandBuilder(caps, Path("/usr/bin/ffmpeg"))

        cmd = builder.audio_extract_args(
            input_path=Path("/test/video.mkv"),
            track_index=1,
            duration=30,
        )

        assert "-t" in cmd
        assert "30" in cmd

    def test_custom_sample_rate(self) -> None:
        """Supports custom sample rate."""
        caps = FFmpegCapabilities()
        builder = FFmpegCommandBuilder(caps, Path("/usr/bin/ffmpeg"))

        cmd = builder.audio_extract_args(
            input_path=Path("/test/video.mkv"),
            track_index=1,
            sample_rate=48000,
        )

        assert "48000" in cmd

    def test_stereo_channels(self) -> None:
        """Supports stereo output."""
        caps = FFmpegCapabilities()
        builder = FFmpegCommandBuilder(caps, Path("/usr/bin/ffmpeg"))

        cmd = builder.audio_extract_args(
            input_path=Path("/test/video.mkv"),
            track_index=1,
            channels=2,
        )

        ac_idx = cmd.index("-ac")
        assert cmd[ac_idx + 1] == "2"

    def test_respects_pcm_codec_requirement(self) -> None:
        """Uses explicit codec when required."""
        caps = FFmpegCapabilities(requires_explicit_pcm_codec=True)
        builder = FFmpegCommandBuilder(caps, Path("/usr/bin/ffmpeg"))

        cmd = builder.audio_extract_args(
            input_path=Path("/test/video.mkv"),
            track_index=1,
        )

        assert "-acodec" in cmd
        assert "pcm_s16le" in cmd
