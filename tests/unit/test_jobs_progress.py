"""Backward compatibility tests for progress parsing.

DEPRECATED: Tests have moved to tests/unit/tools/test_ffmpeg_progress.py
This file re-exports tests for backward compatibility.
"""

# Re-import all tests from new location to maintain backward compatibility
from tests.unit.tools.test_ffmpeg_progress import (  # noqa: F401
    TestFFmpegProgress,
    TestIntegration,
    TestParseProgressBlock,
    TestParseProgressLine,
    TestParseStderrProgress,
)
