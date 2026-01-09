"""FFmpeg progress parsing utilities.

DEPRECATED: This module has moved to vpo.tools.ffmpeg_progress.
This shim provides backward compatibility. Update imports to use the new location.
"""

import warnings

# Re-export from new location for backward compatibility
from vpo.tools.ffmpeg_progress import (
    PROGRESS_PATTERNS,
    FFmpegProgress,
    parse_progress_block,
    parse_progress_line,
    parse_stderr_progress,
)

# Issue deprecation warning on import
warnings.warn(
    "vpo.jobs.progress is deprecated. Use vpo.tools.ffmpeg_progress instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "FFmpegProgress",
    "PROGRESS_PATTERNS",
    "parse_progress_block",
    "parse_progress_line",
    "parse_stderr_progress",
]
