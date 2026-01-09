"""External tool detection and capability management.

This module provides infrastructure for detecting, caching, and querying
capabilities of external tools (ffmpeg, ffprobe, mkvmerge, mkvpropedit).
"""

from vpo.tools.cache import (
    ToolCapabilityCache,
    get_tool_registry,
)
from vpo.tools.detection import (
    detect_all_tools,
    detect_ffmpeg,
    detect_ffprobe,
    detect_mkvmerge,
    detect_mkvpropedit,
    parse_version_string,
)

# Encoder detection and selection
from vpo.tools.encoders import (
    HARDWARE_ENCODERS,
    HW_ENCODER_ERROR_PATTERNS,
    SOFTWARE_ENCODERS,
    EncoderSelection,
    check_encoder_available,
    detect_hw_encoder_error,
    get_software_encoder,
    select_encoder,
    select_encoder_with_fallback,
)

# FFmpeg progress parsing
from vpo.tools.ffmpeg_progress import (
    PROGRESS_PATTERNS,
    FFmpegProgress,
    parse_progress_block,
    parse_progress_line,
    parse_stderr_progress,
)
from vpo.tools.models import (
    FFmpegCapabilities,
    FFmpegInfo,
    FFprobeInfo,
    MkvmergeInfo,
    MkvpropeditInfo,
    ToolInfo,
    ToolRegistry,
    ToolStatus,
)
from vpo.tools.requirements import (
    RequirementLevel,
    RequirementsReport,
    ToolRequirement,
    check_core_requirements,
    check_mkv_requirements,
    check_non_mkv_requirements,
    check_requirements,
    get_missing_tool_hints,
    get_upgrade_suggestions,
)

__all__ = [
    # FFmpeg progress parsing
    "FFmpegProgress",
    "PROGRESS_PATTERNS",
    "parse_progress_line",
    "parse_progress_block",
    "parse_stderr_progress",
    # Models
    "FFmpegCapabilities",
    "FFmpegInfo",
    "FFprobeInfo",
    "MkvmergeInfo",
    "MkvpropeditInfo",
    "ToolInfo",
    "ToolRegistry",
    "ToolStatus",
    # Detection
    "detect_all_tools",
    "detect_ffmpeg",
    "detect_ffprobe",
    "detect_mkvmerge",
    "detect_mkvpropedit",
    "parse_version_string",
    # Cache
    "ToolCapabilityCache",
    "get_tool_registry",
    # Requirements
    "RequirementLevel",
    "RequirementsReport",
    "ToolRequirement",
    "check_requirements",
    "check_core_requirements",
    "check_mkv_requirements",
    "check_non_mkv_requirements",
    "get_missing_tool_hints",
    "get_upgrade_suggestions",
    # Encoders
    "HARDWARE_ENCODERS",
    "HW_ENCODER_ERROR_PATTERNS",
    "SOFTWARE_ENCODERS",
    "EncoderSelection",
    "check_encoder_available",
    "detect_hw_encoder_error",
    "get_software_encoder",
    "select_encoder",
    "select_encoder_with_fallback",
]
