"""External tool detection and capability management.

This module provides infrastructure for detecting, caching, and querying
capabilities of external tools (ffmpeg, ffprobe, mkvmerge, mkvpropedit).
"""

from video_policy_orchestrator.tools.cache import (
    ToolCapabilityCache,
    get_tool_registry,
)
from video_policy_orchestrator.tools.detection import (
    detect_all_tools,
    detect_ffmpeg,
    detect_ffprobe,
    detect_mkvmerge,
    detect_mkvpropedit,
    parse_version_string,
)
from video_policy_orchestrator.tools.models import (
    FFmpegCapabilities,
    FFmpegInfo,
    FFprobeInfo,
    MkvmergeInfo,
    MkvpropeditInfo,
    ToolInfo,
    ToolRegistry,
    ToolStatus,
)
from video_policy_orchestrator.tools.requirements import (
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
]
