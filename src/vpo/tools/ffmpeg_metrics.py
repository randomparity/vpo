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
        if not bitrate_str or bitrate_str.strip() in ("N/A", ""):
            return None

        bitrate_lower = bitrate_str.lower().strip()

        try:
            # Determine multiplier based on unit suffix
            if "mbits/s" in bitrate_lower:
                value = float(bitrate_lower.replace("mbits/s", "").strip())
                multiplier = 1000
            elif "kbits/s" in bitrate_lower:
                value = float(bitrate_lower.replace("kbits/s", "").strip())
                multiplier = 1
            else:
                # Plain number - assume kbps
                value = float(bitrate_str.strip())
                multiplier = 1

            result = round(value * multiplier)
            return result if result >= 0 else None
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
