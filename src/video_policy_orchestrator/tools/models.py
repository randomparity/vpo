"""Data models for external tool capabilities.

This module defines dataclasses for representing detected tool information,
capabilities, and the aggregated tool registry.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class ToolStatus(Enum):
    """Status of an external tool."""

    AVAILABLE = "available"  # Tool found and version detected
    MISSING = "missing"  # Tool not found in PATH or configured location
    OUTDATED = "outdated"  # Tool found but version below minimum required
    ERROR = "error"  # Tool found but detection failed


@dataclass
class ToolInfo:
    """Base information for any external tool."""

    name: str
    path: Path | None = None
    version: str | None = None
    version_tuple: tuple[int, ...] | None = None  # Parsed version for comparison
    status: ToolStatus = ToolStatus.MISSING
    status_message: str | None = None
    detected_at: datetime | None = None

    def is_available(self) -> bool:
        """Return True if the tool is available and usable."""
        return self.status == ToolStatus.AVAILABLE

    def meets_version(self, min_version: tuple[int, ...]) -> bool:
        """Check if tool version meets minimum requirement.

        Args:
            min_version: Minimum version as tuple (e.g., (6, 0) for 6.0).

        Returns:
            True if tool version >= min_version, False otherwise.
        """
        if self.version_tuple is None:
            return False
        # Compare tuple by tuple, padding shorter with zeros
        max_len = max(len(self.version_tuple), len(min_version))
        v1 = self.version_tuple + (0,) * (max_len - len(self.version_tuple))
        v2 = min_version + (0,) * (max_len - len(min_version))
        return v1 >= v2


@dataclass
class FFmpegCapabilities:
    """Detailed capabilities of ffmpeg build.

    Captures build configuration, supported codecs, formats, and filters
    to enable feature detection and graceful degradation.
    """

    # Build configuration
    configuration: str = ""  # Full --configure line
    build_flags: list[str] = field(default_factory=list)  # Parsed --enable flags
    is_gpl: bool = False  # Built with GPL license (enables x264, x265, etc.)
    is_nonfree: bool = False  # Built with non-free components

    # Codec support
    encoders: set[str] = field(default_factory=set)  # Available encoders
    decoders: set[str] = field(default_factory=set)  # Available decoders

    # Format support
    muxers: set[str] = field(default_factory=set)  # Output formats
    demuxers: set[str] = field(default_factory=set)  # Input formats

    # Filter support
    filters: set[str] = field(default_factory=set)  # Available filters

    # Common codec checks (convenience methods)
    def has_encoder(self, name: str) -> bool:
        """Check if encoder is available."""
        return name.lower() in self.encoders

    def has_decoder(self, name: str) -> bool:
        """Check if decoder is available."""
        return name.lower() in self.decoders

    def has_muxer(self, name: str) -> bool:
        """Check if muxer (output format) is available."""
        return name.lower() in self.muxers

    def has_demuxer(self, name: str) -> bool:
        """Check if demuxer (input format) is available."""
        return name.lower() in self.demuxers

    def has_filter(self, name: str) -> bool:
        """Check if filter is available."""
        return name.lower() in self.filters

    # VPO-specific capability checks
    def can_remux_to_mkv(self) -> bool:
        """Check if ffmpeg can remux to MKV container."""
        return self.has_muxer("matroska")

    def can_copy_streams(self) -> bool:
        """Check if stream copy is available (always True for ffmpeg)."""
        return True

    def supports_metadata_modification(self) -> bool:
        """Check if metadata modification is supported."""
        # FFmpeg always supports basic metadata via -metadata flag
        return True


@dataclass
class FFprobeInfo(ToolInfo):
    """FFprobe tool information.

    FFprobe shares ffmpeg's build but has simpler capability needs.
    """

    def __init__(self, **kwargs):
        super().__init__(name="ffprobe", **kwargs)


@dataclass
class FFmpegInfo(ToolInfo):
    """FFmpeg tool information with detailed capabilities."""

    capabilities: FFmpegCapabilities = field(default_factory=FFmpegCapabilities)

    def __init__(self, capabilities: FFmpegCapabilities | None = None, **kwargs):
        # Set name before calling parent init
        super().__init__(name="ffmpeg", **kwargs)
        self.capabilities = capabilities or FFmpegCapabilities()


@dataclass
class MkvmergeInfo(ToolInfo):
    """Mkvmerge tool information."""

    # Mkvmerge capabilities are version-dependent but simpler than ffmpeg
    supports_track_order: bool = True  # --track-order flag
    supports_json_output: bool = True  # -J flag for JSON output

    def __init__(self, **kwargs):
        super().__init__(name="mkvmerge", **kwargs)


@dataclass
class MkvpropeditInfo(ToolInfo):
    """Mkvpropedit tool information."""

    # Mkvpropedit capabilities
    supports_track_edit: bool = True  # --edit track:N
    supports_add_attachment: bool = True  # --add-attachment

    def __init__(self, **kwargs):
        super().__init__(name="mkvpropedit", **kwargs)


@dataclass
class ToolRegistry:
    """Aggregated registry of all external tools and their capabilities.

    This is the main entry point for querying tool availability and
    capabilities throughout VPO.
    """

    ffmpeg: FFmpegInfo = field(default_factory=FFmpegInfo)
    ffprobe: FFprobeInfo = field(default_factory=FFprobeInfo)
    mkvmerge: MkvmergeInfo = field(default_factory=MkvmergeInfo)
    mkvpropedit: MkvpropeditInfo = field(default_factory=MkvpropeditInfo)

    # Metadata
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cache_valid_until: datetime | None = None

    def get_tool(self, name: str) -> ToolInfo | None:
        """Get tool info by name.

        Args:
            name: Tool name (ffmpeg, ffprobe, mkvmerge, mkvpropedit).

        Returns:
            ToolInfo for the tool, or None if unknown tool name.
        """
        tools = {
            "ffmpeg": self.ffmpeg,
            "ffprobe": self.ffprobe,
            "mkvmerge": self.mkvmerge,
            "mkvpropedit": self.mkvpropedit,
        }
        return tools.get(name.lower())

    def is_available(self, name: str) -> bool:
        """Check if a tool is available.

        Args:
            name: Tool name.

        Returns:
            True if tool is available and usable.
        """
        tool = self.get_tool(name)
        return tool is not None and tool.is_available()

    def get_available_tools(self) -> list[str]:
        """Get list of available tool names.

        Returns:
            List of tool names that are available.
        """
        return [
            name
            for name in ["ffmpeg", "ffprobe", "mkvmerge", "mkvpropedit"]
            if self.is_available(name)
        ]

    def get_missing_tools(self) -> list[str]:
        """Get list of missing tool names.

        Returns:
            List of tool names that are not available.
        """
        return [
            name
            for name in ["ffmpeg", "ffprobe", "mkvmerge", "mkvpropedit"]
            if not self.is_available(name)
        ]

    def all_tools_available(self) -> bool:
        """Check if all external tools are available.

        Returns:
            True if all tools are available.
        """
        return len(self.get_missing_tools()) == 0

    def summary(self) -> dict[str, dict[str, str | bool]]:
        """Get summary of all tools for display.

        Returns:
            Dict mapping tool name to status info.
        """
        return {
            "ffmpeg": {
                "available": self.ffmpeg.is_available(),
                "version": self.ffmpeg.version or "not found",
                "path": str(self.ffmpeg.path) if self.ffmpeg.path else "not found",
            },
            "ffprobe": {
                "available": self.ffprobe.is_available(),
                "version": self.ffprobe.version or "not found",
                "path": str(self.ffprobe.path) if self.ffprobe.path else "not found",
            },
            "mkvmerge": {
                "available": self.mkvmerge.is_available(),
                "version": self.mkvmerge.version or "not found",
                "path": str(self.mkvmerge.path) if self.mkvmerge.path else "not found",
            },
            "mkvpropedit": {
                "available": self.mkvpropedit.is_available(),
                "version": self.mkvpropedit.version or "not found",
                "path": (
                    str(self.mkvpropedit.path) if self.mkvpropedit.path else "not found"
                ),
            },
        }
