"""Configuration data models.

This module defines dataclasses for VPO configuration options.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ToolPathsConfig:
    """Configuration for external tool paths.

    All paths are optional. If not specified, tools are looked up in PATH.
    """

    ffmpeg: Path | None = None
    ffprobe: Path | None = None
    mkvmerge: Path | None = None
    mkvpropedit: Path | None = None


@dataclass
class DetectionConfig:
    """Configuration for tool capability detection."""

    # Cache TTL in hours (default 24)
    cache_ttl_hours: int = 24

    # Whether to auto-detect tools on startup
    auto_detect_on_startup: bool = True


@dataclass
class BehaviorConfig:
    """Configuration for VPO runtime behavior."""

    # Warn when features are missing (but operation can proceed)
    warn_on_missing_features: bool = True

    # Show upgrade suggestions when tools are outdated
    show_upgrade_suggestions: bool = True


@dataclass
class PluginConfig:
    """Configuration for plugin system."""

    # Additional directories to search for plugins
    # Default: ~/.vpo/plugins/
    plugin_dirs: list[Path] = field(default_factory=list)

    # Entry point group name for plugin discovery
    entry_point_group: str = "vpo.plugins"

    # Whether to auto-load plugins on startup
    auto_load: bool = True

    # Whether to warn about unacknowledged directory plugins
    warn_unacknowledged: bool = True


@dataclass
class JobsConfig:
    """Configuration for job system."""

    # How long to keep completed jobs (days)
    retention_days: int = 30

    # Purge old jobs on worker start
    auto_purge: bool = True

    # Temp directory for transcoding output (None = use source directory)
    temp_directory: Path | None = None

    # Keep backup of original after successful transcode
    backup_original: bool = True

    # Disk space estimation ratio for HEVC/AV1 codecs (typically compress better)
    disk_space_ratio_hevc: float = 0.5

    # Disk space estimation ratio for other codecs
    disk_space_ratio_other: float = 0.8

    # Buffer multiplier for disk space estimation
    disk_space_buffer: float = 1.2


@dataclass
class WorkerConfig:
    """Configuration for job worker defaults."""

    # Maximum number of files to process per worker run
    max_files: int | None = None

    # Maximum duration in seconds per worker run
    max_duration: int | None = None

    # End time for worker (HH:MM format, 24h)
    end_by: str | None = None

    # Number of CPU cores to use for transcoding
    cpu_cores: int | None = None


@dataclass
class VPOConfig:
    """Main configuration container for VPO.

    Aggregates all configuration sections.
    """

    tools: ToolPathsConfig = field(default_factory=ToolPathsConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
    plugins: PluginConfig = field(default_factory=PluginConfig)
    jobs: JobsConfig = field(default_factory=JobsConfig)
    worker: WorkerConfig = field(default_factory=WorkerConfig)

    # Database path (can be overridden)
    database_path: Path | None = None

    def get_tool_path(self, tool_name: str) -> Path | None:
        """Get configured path for a tool.

        Args:
            tool_name: Name of the tool (ffmpeg, ffprobe, mkvmerge, mkvpropedit).

        Returns:
            Configured path or None if not configured.
        """
        return getattr(self.tools, tool_name.lower(), None)
