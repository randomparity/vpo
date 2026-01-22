"""Transcode data types and result classes.

This module defines the core data structures used throughout the transcode
executor, including plans, results, and two-pass encoding context.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from vpo.db import TrackInfo
from vpo.policy.transcode import AudioPlan, SkipEvaluationResult
from vpo.policy.video_analysis import HDRType

logger = logging.getLogger(__name__)


@dataclass
class TwoPassContext:
    """Context for two-pass encoding.

    Two-pass encoding requires running FFmpeg twice:
    - Pass 1: Analyze video, output to /dev/null, create log file
    - Pass 2: Encode video using the log file for accurate bitrate targeting
    """

    passlogfile: Path
    """Path prefix for pass log files (FFmpeg adds suffixes)."""

    current_pass: int = 1
    """Current pass number (1 or 2)."""

    def cleanup(self) -> None:
        """Remove pass log files after encoding.

        x265 creates: passlogfile.log, passlogfile.log.cutree
        x264 creates: passlogfile-0.log, passlogfile-0.log.mbtree
        """
        suffixes = [".log", ".log.cutree", "-0.log", "-0.log.mbtree"]
        for suffix in suffixes:
            log_file = Path(str(self.passlogfile) + suffix)
            if log_file.exists():
                try:
                    log_file.unlink()
                    logger.debug("Cleaned up pass log file: %s", log_file)
                except OSError as e:
                    logger.warning(
                        "Could not clean up pass log file %s: %s", log_file, e
                    )


@dataclass
class TranscodeResult:
    """Result of a transcode operation."""

    success: bool
    output_path: Path | None = None
    error_message: str | None = None
    backup_path: Path | None = None


@dataclass
class TranscodePlan:
    """Plan for transcoding a file."""

    input_path: Path
    output_path: Path
    policy: "TranscodePolicyConfig"  # Forward reference to avoid circular import

    # Video track info (from introspection)
    video_codec: str | None = None
    video_width: int | None = None
    video_height: int | None = None
    video_bitrate: int | None = None
    duration_seconds: float | None = None

    # Audio tracks info
    audio_tracks: list[TrackInfo] | None = None

    # V6 skip condition evaluation result
    skip_result: SkipEvaluationResult | None = None

    # Computed video actions
    needs_video_transcode: bool = False
    needs_video_scale: bool = False
    target_width: int | None = None
    target_height: int | None = None

    # Computed audio plan
    audio_plan: AudioPlan | None = None

    # Edge case detection results
    warnings: list[str] | None = None
    is_vfr: bool = False
    is_hdr: bool = False
    hdr_type: HDRType = HDRType.NONE
    bitrate_estimated: bool = False
    primary_video_index: int | None = None

    @property
    def needs_any_transcode(self) -> bool:
        """True if any transcoding work is needed."""
        # If skip evaluation says skip, no transcode needed
        if self.skip_result and self.skip_result.skip:
            return False
        if self.needs_video_transcode:
            return True
        if self.audio_plan and self.audio_plan.has_changes:
            return True
        return False

    @property
    def should_skip(self) -> bool:
        """True if transcoding should be skipped due to skip conditions."""
        return self.skip_result is not None and self.skip_result.skip

    @property
    def skip_reason(self) -> str | None:
        """Human-readable skip reason if should_skip is True."""
        if self.skip_result and self.skip_result.skip:
            return self.skip_result.reason
        return None


# Import TranscodePolicyConfig for type annotation at runtime
# This is done at the end to avoid circular imports
from vpo.policy.types import TranscodePolicyConfig  # noqa: E402, F401
