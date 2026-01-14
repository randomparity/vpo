"""Tool version requirements and capability checks.

This module defines minimum version requirements for VPO features and
provides utilities to check if the current tools meet those requirements.
"""

from dataclasses import dataclass, field
from enum import Enum

from vpo.tools.models import ToolRegistry


class RequirementLevel(Enum):
    """Severity level of a requirement."""

    REQUIRED = "required"  # Feature won't work without this
    RECOMMENDED = "recommended"  # Feature works but degraded
    OPTIONAL = "optional"  # Nice to have


@dataclass
class ToolRequirement:
    """A single tool requirement specification."""

    tool_name: str
    feature_name: str
    description: str
    level: RequirementLevel = RequirementLevel.REQUIRED
    min_version: tuple[int, ...] | None = None  # None means any version
    capability_check: str | None = None  # Method name to call on capabilities
    install_hint: str | None = None  # How to install/upgrade


@dataclass
class RequirementCheckResult:
    """Result of checking a single requirement."""

    requirement: ToolRequirement
    satisfied: bool
    current_version: str | None = None
    message: str = ""


@dataclass
class RequirementsReport:
    """Full report of all requirement checks."""

    results: list[RequirementCheckResult] = field(default_factory=list)

    @property
    def all_satisfied(self) -> bool:
        """Check if all requirements are satisfied."""
        return all(r.satisfied for r in self.results)

    @property
    def required_satisfied(self) -> bool:
        """Check if all REQUIRED requirements are satisfied."""
        return all(
            r.satisfied
            for r in self.results
            if r.requirement.level == RequirementLevel.REQUIRED
        )

    def get_unsatisfied(
        self, level: RequirementLevel | None = None
    ) -> list[RequirementCheckResult]:
        """Get unsatisfied requirements, optionally filtered by level."""
        results = [r for r in self.results if not r.satisfied]
        if level:
            results = [r for r in results if r.requirement.level == level]
        return results

    def get_messages(self, level: RequirementLevel | None = None) -> list[str]:
        """Get messages for unsatisfied requirements."""
        return [r.message for r in self.get_unsatisfied(level) if r.message]


# =============================================================================
# VPO Tool Requirements
# =============================================================================

# Core requirements - these are needed for basic VPO functionality
CORE_REQUIREMENTS = [
    ToolRequirement(
        tool_name="ffprobe",
        feature_name="Media Introspection",
        description="ffprobe is required to inspect media file metadata",
        level=RequirementLevel.REQUIRED,
        min_version=None,  # Any version works
        install_hint="Install ffmpeg: https://ffmpeg.org/download.html",
    ),
]

# MKV-specific requirements
MKV_REQUIREMENTS = [
    ToolRequirement(
        tool_name="mkvpropedit",
        feature_name="MKV Metadata Editing",
        description="mkvpropedit is required for fast in-place MKV metadata changes",
        level=RequirementLevel.REQUIRED,
        min_version=None,
        install_hint="Install mkvtoolnix: https://mkvtoolnix.download/",
    ),
    ToolRequirement(
        tool_name="mkvmerge",
        feature_name="MKV Track Reordering",
        description="mkvmerge is required for reordering tracks in MKV files",
        level=RequirementLevel.REQUIRED,
        min_version=None,
        install_hint="Install mkvtoolnix: https://mkvtoolnix.download/",
    ),
]

# Non-MKV requirements
NON_MKV_REQUIREMENTS = [
    ToolRequirement(
        tool_name="ffmpeg",
        feature_name="Non-MKV Metadata Editing",
        description="ffmpeg is required for metadata changes in MP4/AVI/WebM files",
        level=RequirementLevel.REQUIRED,
        min_version=None,
        install_hint="Install ffmpeg: https://ffmpeg.org/download.html",
    ),
]

# Version-specific requirements (recommendations)
VERSION_RECOMMENDATIONS = [
    ToolRequirement(
        tool_name="ffmpeg",
        feature_name="Modern FFmpeg",
        description="FFmpeg 5.0+ recommended for best codec support",
        level=RequirementLevel.RECOMMENDED,
        min_version=(5, 0),
        install_hint="Upgrade ffmpeg: https://ffmpeg.org/download.html",
    ),
    ToolRequirement(
        tool_name="mkvmerge",
        feature_name="Modern mkvtoolnix",
        description="mkvtoolnix 70.0+ recommended for best compatibility",
        level=RequirementLevel.RECOMMENDED,
        min_version=(70, 0),
        install_hint="Upgrade mkvtoolnix: https://mkvtoolnix.download/",
    ),
]

# Capability-specific requirements
CAPABILITY_REQUIREMENTS = [
    ToolRequirement(
        tool_name="ffmpeg",
        feature_name="MKV Muxing",
        description="FFmpeg must support MKV output format",
        level=RequirementLevel.REQUIRED,
        capability_check="can_remux_to_mkv",
        install_hint="Rebuild ffmpeg with libmatroska support",
    ),
]

# FFmpeg version requirements for specific features
FFMPEG_VERSION_REQUIREMENTS = [
    ToolRequirement(
        tool_name="ffmpeg",
        feature_name="FFmpeg Core",
        description="FFmpeg 3.0+ required for basic VPO functionality",
        level=RequirementLevel.REQUIRED,
        min_version=(3, 0),
        install_hint="Install ffmpeg 4.0+: https://ffmpeg.org/download.html",
    ),
    ToolRequirement(
        tool_name="ffprobe",
        feature_name="FFprobe Core",
        description="FFprobe 3.0+ required for media introspection",
        level=RequirementLevel.REQUIRED,
        min_version=(3, 0),
        install_hint="Install ffmpeg 4.0+: https://ffmpeg.org/download.html",
    ),
    ToolRequirement(
        tool_name="ffmpeg",
        feature_name="Progress Reporting",
        description="FFmpeg 4.3+ enables accurate progress reporting",
        level=RequirementLevel.RECOMMENDED,
        min_version=(4, 3),
        install_hint="Upgrade ffmpeg for better progress tracking",
    ),
]

# Transcription-specific requirements
TRANSCRIPTION_REQUIREMENTS = [
    ToolRequirement(
        tool_name="ffmpeg",
        feature_name="Audio Extraction",
        description="FFmpeg required to extract audio tracks for transcription",
        level=RequirementLevel.REQUIRED,
        min_version=(3, 0),
        install_hint="Install ffmpeg: https://ffmpeg.org/download.html",
    ),
]

# All requirements combined
ALL_REQUIREMENTS = (
    CORE_REQUIREMENTS
    + MKV_REQUIREMENTS
    + NON_MKV_REQUIREMENTS
    + VERSION_RECOMMENDATIONS
    + CAPABILITY_REQUIREMENTS
    + FFMPEG_VERSION_REQUIREMENTS
    + TRANSCRIPTION_REQUIREMENTS
)


def check_requirement(
    registry: ToolRegistry, requirement: ToolRequirement
) -> RequirementCheckResult:
    """Check if a single requirement is satisfied.

    Args:
        registry: Tool registry with detected tools.
        requirement: Requirement to check.

    Returns:
        RequirementCheckResult with status and message.
    """
    tool = registry.get_tool(requirement.tool_name)

    # Tool not found
    if tool is None or not tool.is_available():
        return RequirementCheckResult(
            requirement=requirement,
            satisfied=False,
            current_version=None,
            message=(
                f"{requirement.feature_name}: {requirement.tool_name} not found. "
                f"{requirement.install_hint or ''}"
            ),
        )

    # Check version requirement
    if requirement.min_version:
        if not tool.meets_version(requirement.min_version):
            min_ver_str = ".".join(str(v) for v in requirement.min_version)
            return RequirementCheckResult(
                requirement=requirement,
                satisfied=False,
                current_version=tool.version,
                message=(
                    f"{requirement.feature_name}: {requirement.tool_name} "
                    f"version {tool.version} < required {min_ver_str}. "
                    f"{requirement.install_hint or ''}"
                ),
            )

    # Check capability requirement (for ffmpeg)
    if requirement.capability_check and requirement.tool_name == "ffmpeg":
        from vpo.tools.models import FFmpegInfo

        if isinstance(registry.ffmpeg, FFmpegInfo):
            caps = registry.ffmpeg.capabilities
            check_method = getattr(caps, requirement.capability_check, None)
            if check_method and callable(check_method):
                if not check_method():
                    return RequirementCheckResult(
                        requirement=requirement,
                        satisfied=False,
                        current_version=tool.version,
                        message=(
                            f"{requirement.feature_name}: "
                            f"{requirement.description}. "
                            f"{requirement.install_hint or ''}"
                        ),
                    )

    # Requirement satisfied
    return RequirementCheckResult(
        requirement=requirement,
        satisfied=True,
        current_version=tool.version,
        message="",
    )


def check_requirements(
    registry: ToolRegistry,
    requirements: list[ToolRequirement] | None = None,
) -> RequirementsReport:
    """Check all requirements against the tool registry.

    Args:
        registry: Tool registry with detected tools.
        requirements: List of requirements to check. Defaults to ALL_REQUIREMENTS.

    Returns:
        RequirementsReport with all check results.
    """
    if requirements is None:
        requirements = ALL_REQUIREMENTS

    results = [check_requirement(registry, req) for req in requirements]
    return RequirementsReport(results=results)


def check_core_requirements(registry: ToolRegistry) -> RequirementsReport:
    """Check only core requirements.

    Args:
        registry: Tool registry with detected tools.

    Returns:
        RequirementsReport for core requirements only.
    """
    return check_requirements(registry, CORE_REQUIREMENTS)


def check_mkv_requirements(registry: ToolRegistry) -> RequirementsReport:
    """Check requirements for MKV operations.

    Args:
        registry: Tool registry with detected tools.

    Returns:
        RequirementsReport for MKV requirements.
    """
    return check_requirements(registry, MKV_REQUIREMENTS)


def check_non_mkv_requirements(registry: ToolRegistry) -> RequirementsReport:
    """Check requirements for non-MKV operations.

    Args:
        registry: Tool registry with detected tools.

    Returns:
        RequirementsReport for non-MKV requirements.
    """
    return check_requirements(registry, NON_MKV_REQUIREMENTS)


def get_upgrade_suggestions(registry: ToolRegistry) -> list[str]:
    """Get list of upgrade suggestions based on version recommendations.

    Args:
        registry: Tool registry with detected tools.

    Returns:
        List of upgrade suggestion messages.
    """
    report = check_requirements(registry, VERSION_RECOMMENDATIONS)
    return report.get_messages()


def get_missing_tool_hints(registry: ToolRegistry) -> dict[str, str]:
    """Get installation hints for missing tools.

    Args:
        registry: Tool registry with detected tools.

    Returns:
        Dict mapping tool name to installation hint.
    """
    hints = {}
    for tool_name in ["ffmpeg", "ffprobe", "mkvmerge", "mkvpropedit"]:
        if not registry.is_available(tool_name):
            # Find a requirement with an install hint for this tool
            for req in ALL_REQUIREMENTS:
                if req.tool_name == tool_name and req.install_hint:
                    hints[tool_name] = req.install_hint
                    break
    return hints


def check_transcription_requirements(registry: ToolRegistry) -> RequirementsReport:
    """Check requirements for transcription features.

    Args:
        registry: Tool registry with detected tools.

    Returns:
        RequirementsReport for transcription requirements.
    """
    return check_requirements(registry, TRANSCRIPTION_REQUIREMENTS)


def check_ffmpeg_version_requirements(registry: ToolRegistry) -> RequirementsReport:
    """Check FFmpeg version-specific requirements.

    Args:
        registry: Tool registry with detected tools.

    Returns:
        RequirementsReport for FFmpeg version requirements.
    """
    return check_requirements(registry, FFMPEG_VERSION_REQUIREMENTS)
