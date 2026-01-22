"""Unit tests for FFmpeg metrics aggregation (Issue #264)."""

from vpo.tools.ffmpeg_metrics import (
    FFmpegMetricsAggregator,
    FFmpegMetricsSummary,
)
from vpo.tools.ffmpeg_progress import FFmpegProgress


class TestFFmpegMetricsAggregator:
    """Tests for FFmpegMetricsAggregator class."""

    def test_empty_aggregator_returns_none_values(self) -> None:
        """Empty aggregator should return None for all metrics."""
        aggregator = FFmpegMetricsAggregator()
        summary = aggregator.summarize()

        assert summary.avg_fps is None
        assert summary.peak_fps is None
        assert summary.avg_bitrate_kbps is None
        assert summary.total_frames is None
        assert summary.sample_count == 0

    def test_single_sample(self) -> None:
        """Single sample should be used for all metrics."""
        aggregator = FFmpegMetricsAggregator()

        progress = FFmpegProgress(
            frame=100,
            fps=30.0,
            bitrate="5000kbits/s",
            out_time_us=4_000_000,  # 4 seconds in microseconds
            speed="1.5x",
        )
        aggregator.add_sample(progress)

        summary = aggregator.summarize()

        assert summary.avg_fps == 30.0
        assert summary.peak_fps == 30.0
        assert summary.avg_bitrate_kbps == 5000
        assert summary.total_frames == 100
        assert summary.sample_count == 1

    def test_multiple_samples_average(self) -> None:
        """Multiple samples should be averaged correctly."""
        aggregator = FFmpegMetricsAggregator()

        samples = [
            FFmpegProgress(frame=100, fps=20.0, bitrate="4000kbits/s"),
            FFmpegProgress(frame=200, fps=30.0, bitrate="5000kbits/s"),
            FFmpegProgress(frame=300, fps=40.0, bitrate="6000kbits/s"),
        ]

        for progress in samples:
            aggregator.add_sample(progress)

        summary = aggregator.summarize()

        assert summary.avg_fps == 30.0  # (20 + 30 + 40) / 3
        assert summary.peak_fps == 40.0
        assert summary.avg_bitrate_kbps == 5000  # (4000 + 5000 + 6000) / 3
        assert summary.total_frames == 300  # Last frame
        assert summary.sample_count == 3

    def test_zero_fps_ignored(self) -> None:
        """FPS of 0 should be ignored (happens at start of encoding)."""
        aggregator = FFmpegMetricsAggregator()

        samples = [
            FFmpegProgress(frame=0, fps=0.0, bitrate="0kbits/s"),
            FFmpegProgress(frame=100, fps=30.0, bitrate="5000kbits/s"),
        ]

        for progress in samples:
            aggregator.add_sample(progress)

        summary = aggregator.summarize()

        assert summary.avg_fps == 30.0
        assert summary.peak_fps == 30.0
        assert summary.sample_count == 1  # Only non-zero sample counted

    def test_bitrate_parsing_kbits(self) -> None:
        """Bitrate in kbits/s should be parsed correctly."""
        aggregator = FFmpegMetricsAggregator()

        progress = FFmpegProgress(fps=30.0, bitrate="12345kbits/s")
        aggregator.add_sample(progress)

        summary = aggregator.summarize()
        assert summary.avg_bitrate_kbps == 12345

    def test_bitrate_parsing_mbits(self) -> None:
        """Bitrate in Mbits/s should be converted to kbps."""
        aggregator = FFmpegMetricsAggregator()

        progress = FFmpegProgress(fps=30.0, bitrate="5.5Mbits/s")
        aggregator.add_sample(progress)

        summary = aggregator.summarize()
        assert summary.avg_bitrate_kbps == 5500

    def test_bitrate_parsing_na(self) -> None:
        """N/A bitrate should be ignored."""
        aggregator = FFmpegMetricsAggregator()

        progress = FFmpegProgress(fps=30.0, bitrate="N/A")
        aggregator.add_sample(progress)

        summary = aggregator.summarize()
        assert summary.avg_bitrate_kbps is None

    def test_bitrate_parsing_none(self) -> None:
        """None bitrate should be handled gracefully."""
        aggregator = FFmpegMetricsAggregator()

        progress = FFmpegProgress(fps=30.0, bitrate=None)
        aggregator.add_sample(progress)

        summary = aggregator.summarize()
        assert summary.avg_fps == 30.0
        assert summary.avg_bitrate_kbps is None

    def test_reset_clears_samples(self) -> None:
        """Reset should clear all collected samples."""
        aggregator = FFmpegMetricsAggregator()

        progress = FFmpegProgress(frame=100, fps=30.0, bitrate="5000kbits/s")
        aggregator.add_sample(progress)

        aggregator.reset()

        summary = aggregator.summarize()
        assert summary.avg_fps is None
        assert summary.total_frames is None
        assert summary.sample_count == 0

    def test_none_fps_ignored(self) -> None:
        """None FPS should be handled gracefully."""
        aggregator = FFmpegMetricsAggregator()

        progress = FFmpegProgress(frame=100, fps=None, bitrate="5000kbits/s")
        aggregator.add_sample(progress)

        summary = aggregator.summarize()
        assert summary.avg_fps is None
        assert summary.total_frames == 100


class TestFFmpegMetricsSummary:
    """Tests for FFmpegMetricsSummary dataclass."""

    def test_default_values(self) -> None:
        """Default summary should have sensible defaults."""
        summary = FFmpegMetricsSummary()

        assert summary.avg_fps is None
        assert summary.peak_fps is None
        assert summary.avg_bitrate_kbps is None
        assert summary.total_frames is None
        assert summary.sample_count == 0

    def test_with_values(self) -> None:
        """Summary with values should store them correctly."""
        summary = FFmpegMetricsSummary(
            avg_fps=30.0,
            peak_fps=45.0,
            avg_bitrate_kbps=5000,
            total_frames=1000,
            sample_count=100,
        )

        assert summary.avg_fps == 30.0
        assert summary.peak_fps == 45.0
        assert summary.avg_bitrate_kbps == 5000
        assert summary.total_frames == 1000
        assert summary.sample_count == 100
