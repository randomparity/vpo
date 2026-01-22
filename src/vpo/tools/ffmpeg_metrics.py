"""FFmpeg encoding metrics aggregation.

This module provides utilities for collecting and aggregating FFmpeg encoding
metrics during transcode operations (Issue #264).
"""

from dataclasses import dataclass, field

from vpo.tools.ffmpeg_progress import FFmpegProgress


@dataclass
class FFmpegMetricsSummary:
    """Summary of aggregated FFmpeg encoding metrics.

    Attributes:
        avg_fps: Average encoding frames per second.
        peak_fps: Peak encoding frames per second.
        avg_bitrate_kbps: Average output bitrate in kilobits per second.
        total_frames: Total frames encoded.
        sample_count: Number of progress samples collected.
    """

    avg_fps: float | None = None
    peak_fps: float | None = None
    avg_bitrate_kbps: int | None = None
    total_frames: int | None = None
    sample_count: int = 0


@dataclass
class FFmpegMetricsAggregator:
    """Collects and aggregates FFmpeg progress metrics during encoding.

    This class receives FFmpegProgress samples during an encoding operation
    and computes aggregate statistics upon request.

    Usage:
        aggregator = FFmpegMetricsAggregator()
        for progress in progress_samples:
            aggregator.add_sample(progress)
        summary = aggregator.summarize()
    """

    # Collected samples
    fps_samples: list[float] = field(default_factory=list)
    bitrate_samples: list[int] = field(default_factory=list)
    last_frame: int | None = None

    def add_sample(self, progress: FFmpegProgress) -> None:
        """Add a progress sample to the aggregator.

        Args:
            progress: FFmpegProgress object from parsing FFmpeg output.
        """
        if progress.fps is not None and progress.fps > 0:
            self.fps_samples.append(progress.fps)

        # Parse bitrate (e.g., "5000kbits/s" or "5000.5kbits/s")
        if progress.bitrate is not None:
            bitrate_kbps = self._parse_bitrate(progress.bitrate)
            if bitrate_kbps is not None and bitrate_kbps > 0:
                self.bitrate_samples.append(bitrate_kbps)

        if progress.frame is not None:
            self.last_frame = progress.frame

    def _parse_bitrate(self, bitrate_str: str) -> int | None:
        """Parse bitrate string to kilobits per second.

        Args:
            bitrate_str: Bitrate string like "5000kbits/s" or "5.2Mbits/s".

        Returns:
            Bitrate in kbps as integer, or None if parsing fails.
        """
        if not bitrate_str:
            return None

        # Remove any whitespace
        bitrate_str = bitrate_str.strip()

        # Handle N/A or empty
        if bitrate_str in ("N/A", ""):
            return None

        try:
            # Check for Mbits/s
            if "Mbits/s" in bitrate_str or "mbits/s" in bitrate_str.lower():
                value = float(bitrate_str.lower().replace("mbits/s", "").strip())
                return int(value * 1000)

            # Check for kbits/s (most common)
            if "kbits/s" in bitrate_str.lower():
                value = float(bitrate_str.lower().replace("kbits/s", "").strip())
                return int(value)

            # Try parsing as plain number (assume kbps)
            return int(float(bitrate_str))
        except (ValueError, AttributeError):
            return None

    def summarize(self) -> FFmpegMetricsSummary:
        """Compute aggregate metrics from collected samples.

        Returns:
            FFmpegMetricsSummary with computed averages and totals.
        """
        avg_fps: float | None = None
        peak_fps: float | None = None
        avg_bitrate: int | None = None

        if self.fps_samples:
            avg_fps = sum(self.fps_samples) / len(self.fps_samples)
            peak_fps = max(self.fps_samples)

        if self.bitrate_samples:
            avg_bitrate = int(sum(self.bitrate_samples) / len(self.bitrate_samples))

        return FFmpegMetricsSummary(
            avg_fps=avg_fps,
            peak_fps=peak_fps,
            avg_bitrate_kbps=avg_bitrate,
            total_frames=self.last_frame,
            sample_count=len(self.fps_samples),
        )

    def reset(self) -> None:
        """Clear all collected samples."""
        self.fps_samples.clear()
        self.bitrate_samples.clear()
        self.last_frame = None
