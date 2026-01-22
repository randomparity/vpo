"""Integration tests for transcode metrics capture flow.

Tests that FFmpeg encoding metrics (fps, bitrate, frames) are captured
during transcoding and properly stored in the database.
"""

from __future__ import annotations

from pathlib import Path

from vpo.executor.transcode import TranscodeResult
from vpo.executor.transcode.executor import (
    HARDWARE_ENCODER_PATTERNS,
    detect_encoder_type,
)
from vpo.tools.ffmpeg_metrics import FFmpegMetricsAggregator
from vpo.tools.ffmpeg_progress import FFmpegProgress


class TestEncoderTypeDetection:
    """Test encoder type detection from FFmpeg commands."""

    def test_detects_nvenc_as_hardware(self) -> None:
        """NVENC encoder should be detected as hardware."""
        cmd = ["ffmpeg", "-i", "input.mkv", "-c:v", "hevc_nvenc", "output.mkv"]
        assert detect_encoder_type(cmd) == "hardware"

    def test_detects_vaapi_as_hardware(self) -> None:
        """VAAPI encoder should be detected as hardware."""
        cmd = ["ffmpeg", "-i", "input.mkv", "-c:v", "h264_vaapi", "output.mkv"]
        assert detect_encoder_type(cmd) == "hardware"

    def test_detects_qsv_as_hardware(self) -> None:
        """QSV encoder should be detected as hardware."""
        cmd = ["ffmpeg", "-i", "input.mkv", "-c:v", "hevc_qsv", "output.mkv"]
        assert detect_encoder_type(cmd) == "hardware"

    def test_detects_amf_as_hardware(self) -> None:
        """AMF encoder should be detected as hardware."""
        cmd = ["ffmpeg", "-i", "input.mkv", "-c:v", "h264_amf", "output.mkv"]
        assert detect_encoder_type(cmd) == "hardware"

    def test_detects_videotoolbox_as_hardware(self) -> None:
        """VideoToolbox encoder should be detected as hardware."""
        cmd = ["ffmpeg", "-i", "input.mkv", "-c:v", "hevc_videotoolbox", "output.mkv"]
        assert detect_encoder_type(cmd) == "hardware"

    def test_detects_libx265_as_software(self) -> None:
        """libx265 encoder should be detected as software."""
        cmd = ["ffmpeg", "-i", "input.mkv", "-c:v", "libx265", "output.mkv"]
        assert detect_encoder_type(cmd) == "software"

    def test_detects_libx264_as_software(self) -> None:
        """libx264 encoder should be detected as software."""
        cmd = ["ffmpeg", "-i", "input.mkv", "-c:v", "libx264", "output.mkv"]
        assert detect_encoder_type(cmd) == "software"

    def test_detects_libvpx_as_software(self) -> None:
        """libvpx encoder should be detected as software."""
        cmd = ["ffmpeg", "-i", "input.mkv", "-c:v", "libvpx-vp9", "output.mkv"]
        assert detect_encoder_type(cmd) == "software"

    def test_copy_returns_unknown(self) -> None:
        """Stream copy should return unknown encoder type."""
        cmd = ["ffmpeg", "-i", "input.mkv", "-c:v", "copy", "output.mkv"]
        assert detect_encoder_type(cmd) == "unknown"

    def test_no_video_codec_returns_unknown(self) -> None:
        """Command without video codec flag should return unknown."""
        cmd = ["ffmpeg", "-i", "input.mkv", "output.mkv"]
        assert detect_encoder_type(cmd) == "unknown"

    def test_alternate_codec_flag_formats(self) -> None:
        """Should detect codec with alternate flag formats."""
        # -codec:v format
        cmd1 = ["ffmpeg", "-i", "input.mkv", "-codec:v", "hevc_nvenc", "output.mkv"]
        assert detect_encoder_type(cmd1) == "hardware"

        # -vcodec format
        cmd2 = ["ffmpeg", "-i", "input.mkv", "-vcodec", "libx265", "output.mkv"]
        assert detect_encoder_type(cmd2) == "software"


class TestMetricsAggregatorIntegration:
    """Test metrics aggregator behavior in realistic scenarios."""

    def test_typical_encoding_session(self) -> None:
        """Simulate a typical encoding session with progress updates."""
        aggregator = FFmpegMetricsAggregator()

        # Simulate encoding progress - fps ramps up, then stabilizes
        progress_updates = [
            FFmpegProgress(frame=0, fps=0.0, bitrate="0kbits/s"),  # Start
            FFmpegProgress(frame=100, fps=15.0, bitrate="3000kbits/s"),  # Ramping
            FFmpegProgress(frame=500, fps=28.0, bitrate="4500kbits/s"),  # Stabilizing
            FFmpegProgress(frame=1000, fps=30.0, bitrate="5000kbits/s"),  # Stable
            FFmpegProgress(frame=2000, fps=31.0, bitrate="5200kbits/s"),  # Stable
            FFmpegProgress(frame=3000, fps=29.0, bitrate="4800kbits/s"),  # End
        ]

        for progress in progress_updates:
            aggregator.add_sample(progress)

        summary = aggregator.summarize()

        # Zero FPS sample should be ignored
        assert summary.sample_count == 5
        assert summary.total_frames == 3000

        # Average FPS: (15 + 28 + 30 + 31 + 29) / 5 = 26.6
        assert summary.avg_fps is not None
        assert 26.0 <= summary.avg_fps <= 27.0

        # Peak FPS should be 31
        assert summary.peak_fps == 31.0

        # Average bitrate: (3000 + 4500 + 5000 + 5200 + 4800) / 5 = 4500
        assert summary.avg_bitrate_kbps is not None
        assert 4400 <= summary.avg_bitrate_kbps <= 4600

    def test_hardware_encoding_higher_fps(self) -> None:
        """Hardware encoding typically has higher FPS."""
        aggregator = FFmpegMetricsAggregator()

        # Simulate hardware encoding with higher FPS
        for i in range(10):
            progress = FFmpegProgress(
                frame=(i + 1) * 1000,
                fps=120.0 + (i * 5),  # High FPS typical of hardware
                bitrate="8000kbits/s",
            )
            aggregator.add_sample(progress)

        summary = aggregator.summarize()

        assert summary.peak_fps is not None
        assert summary.peak_fps >= 160.0  # 120 + 9*5 = 165
        assert summary.avg_fps is not None
        assert summary.avg_fps >= 140.0

    def test_variable_bitrate_encoding(self) -> None:
        """Test VBR encoding with varying bitrates."""
        aggregator = FFmpegMetricsAggregator()

        # VBR encoding with varying bitrates
        bitrates = ["2000kbits/s", "8000kbits/s", "3000kbits/s", "15000kbits/s"]
        for i, br in enumerate(bitrates):
            progress = FFmpegProgress(frame=(i + 1) * 500, fps=30.0, bitrate=br)
            aggregator.add_sample(progress)

        summary = aggregator.summarize()

        # Average: (2000 + 8000 + 3000 + 15000) / 4 = 7000
        assert summary.avg_bitrate_kbps == 7000


class TestTranscodeResultMetrics:
    """Test that TranscodeResult properly carries metrics."""

    def test_result_with_metrics(self) -> None:
        """TranscodeResult should carry encoding metrics."""
        result = TranscodeResult(
            success=True,
            output_path=Path("/output/file.mkv"),
            encoding_fps=30.0,
            encoding_bitrate_kbps=5000,
            total_frames=10000,
            encoder_type="hardware",
        )

        assert result.encoding_fps == 30.0
        assert result.encoding_bitrate_kbps == 5000
        assert result.total_frames == 10000
        assert result.encoder_type == "hardware"

    def test_result_without_metrics(self) -> None:
        """TranscodeResult should handle missing metrics gracefully."""
        result = TranscodeResult(
            success=True,
            output_path=Path("/output/file.mkv"),
        )

        assert result.encoding_fps is None
        assert result.encoding_bitrate_kbps is None
        assert result.total_frames is None
        assert result.encoder_type is None

    def test_failed_result_no_metrics(self) -> None:
        """Failed transcode should have no metrics."""
        result = TranscodeResult(
            success=False,
            error_message="FFmpeg failed with exit code 1",
        )

        assert result.success is False
        assert result.encoding_fps is None
        assert result.encoder_type is None


class TestHardwareEncoderPatterns:
    """Test that hardware encoder patterns are comprehensive."""

    def test_all_patterns_detected(self) -> None:
        """All hardware encoder patterns should be properly defined."""
        expected_patterns = {"_nvenc", "_vaapi", "_qsv", "_amf", "_videotoolbox"}
        actual_patterns = set(HARDWARE_ENCODER_PATTERNS)
        assert actual_patterns == expected_patterns

    def test_patterns_match_encoder_names(self) -> None:
        """Patterns should match actual encoder names."""
        encoder_names = [
            "hevc_nvenc",
            "h264_nvenc",
            "h264_vaapi",
            "hevc_vaapi",
            "h264_qsv",
            "hevc_qsv",
            "h264_amf",
            "hevc_amf",
            "h264_videotoolbox",
            "hevc_videotoolbox",
        ]

        for encoder in encoder_names:
            matches = any(pattern in encoder for pattern in HARDWARE_ENCODER_PATTERNS)
            assert matches, f"Pattern should match encoder: {encoder}"
