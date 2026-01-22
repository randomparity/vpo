"""Transcode executor package for video/audio transcoding via FFmpeg.

This package provides the TranscodeExecutor class and supporting utilities
for video transcoding operations. Business logic for skip evaluation, codec
matching, and video analysis has been extracted to:

- policy/video_analysis.py: VFR, HDR, bitrate detection
- policy/codecs.py: Unified codec matching
- policy/transcode.py: Skip condition evaluation
- tools/encoders.py: Hardware encoder detection and selection

Module organization:
- types.py: Data classes (TwoPassContext, TranscodeResult, TranscodePlan)
- decisions.py: Video transcode decision logic (should_transcode_video)
- audio.py: Audio argument building for FFmpeg
- command.py: FFmpeg command construction
- executor.py: TranscodeExecutor class

Usage:
    from vpo.executor.transcode import TranscodeExecutor, TranscodePlan
    from vpo.executor.transcode import build_ffmpeg_command, should_transcode_video
"""

# Types
# Audio utilities
from .audio import (
    build_audio_args,
    build_downmix_filter,
    get_audio_encoder,
)

# Command building
from .command import (
    build_ffmpeg_command,
    build_ffmpeg_command_pass1,
    build_quality_args,
)

# Decisions
from .decisions import (
    should_transcode_video,
)

# Executor
from .executor import (
    TranscodeExecutor,
)
from .types import (
    TranscodePlan,
    TranscodeResult,
    TwoPassContext,
)

__all__ = [
    # Types
    "TranscodePlan",
    "TranscodeResult",
    "TwoPassContext",
    # Decisions
    "should_transcode_video",
    # Audio utilities
    "build_audio_args",
    "build_downmix_filter",
    "get_audio_encoder",
    # Command building
    "build_ffmpeg_command",
    "build_ffmpeg_command_pass1",
    "build_quality_args",
    # Executor
    "TranscodeExecutor",
]
