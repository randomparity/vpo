"""Configuration data models.

This module defines dataclasses for VPO configuration options.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class LanguageConfig:
    """Configuration for language code handling.

    VPO normalizes all language codes to a consistent ISO standard.
    The default is ISO 639-2/B (3-letter bibliographic codes like "eng", "ger")
    which is used natively by MKV containers and FFmpeg.
    """

    standard: Literal["639-1", "639-2/B", "639-2/T"] = "639-2/B"
    """ISO standard to normalize language codes to.

    - "639-1": 2-letter codes (en, de, ja). Compact but not all languages have codes.
    - "639-2/B": 3-letter bibliographic codes (eng, ger, jpn). Default. Used by MKV.
    - "639-2/T": 3-letter terminological codes (eng, deu, jpn). Preferred by linguists.
    """

    warn_on_conversion: bool = True
    """Log warnings when converting between different ISO standards."""

    def __post_init__(self) -> None:
        """Validate configuration."""
        valid_standards = {"639-1", "639-2/B", "639-2/T"}
        if self.standard not in valid_standards:
            raise ValueError(
                f"standard must be one of {valid_standards}, got {self.standard}"
            )


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


@dataclass(frozen=True)
class PluginConnectionConfig:
    """Configuration for connecting to an external metadata service.

    Used by Radarr and Sonarr metadata plugins to configure API access.
    """

    url: str
    """Base URL of the service (e.g., "http://localhost:7878")."""

    api_key: str
    """API key for authentication (found in Settings > General > Security)."""

    enabled: bool = True
    """Whether the plugin is enabled."""

    timeout_seconds: int = 30
    """Request timeout in seconds (1-300)."""

    def __post_init__(self) -> None:
        """Validate configuration."""
        if not self.url.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        if not self.api_key or not self.api_key.strip():
            raise ValueError("API key is required")
        if " " in self.api_key:
            raise ValueError("API key must not contain whitespace")
        if not 1 <= self.timeout_seconds <= 300:
            raise ValueError("Timeout must be between 1 and 300 seconds")


@dataclass
class MetadataPluginSettings:
    """Settings for all metadata enrichment plugins.

    Configure connections to Radarr (movies) and Sonarr (TV series) for
    automatic metadata enrichment during file scans.
    """

    radarr: PluginConnectionConfig | None = None
    """Radarr connection configuration for movie metadata."""

    sonarr: PluginConnectionConfig | None = None
    """Sonarr connection configuration for TV series metadata."""


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

    # Metadata plugin connections (Radarr, Sonarr)
    metadata: MetadataPluginSettings = field(default_factory=MetadataPluginSettings)


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

    # Days before compressing job log files (gzip)
    log_compression_days: int = 7

    # Days before deleting job log files (after compression)
    log_deletion_days: int = 90


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
class ProcessingConfig:
    """Configuration for batch processing behavior.

    Controls parallel file processing in the `vpo process` command.
    """

    workers: int = 2
    """Number of parallel workers for batch processing (1 = sequential)."""

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.workers < 1:
            raise ValueError(f"workers must be at least 1, got {self.workers}")


@dataclass
class LoggingConfig:
    """Configuration for structured logging (008-operational-ux)."""

    # Log level: debug, info, warning, error
    level: str = "info"

    # Log file path (None = stderr only)
    file: Path | None = None

    # Log format: text or json
    format: str = "text"

    # Also log to stderr when file is set
    include_stderr: bool = False

    # Rotation threshold in bytes (default 10MB)
    max_bytes: int = 10_485_760

    # Number of rotated files to keep
    backup_count: int = 5

    def __post_init__(self) -> None:
        """Validate configuration."""
        valid_levels = {"debug", "info", "warning", "error"}
        if self.level.lower() not in valid_levels:
            raise ValueError(f"level must be one of {valid_levels}, got {self.level}")
        valid_formats = {"text", "json"}
        if self.format.lower() not in valid_formats:
            raise ValueError(
                f"format must be one of {valid_formats}, got {self.format}"
            )


@dataclass(frozen=True)
class Profile:
    """Named configuration profile (008-operational-ux).

    Profiles allow users to store named configurations for different libraries.

    This dataclass is immutable (frozen) to prevent accidental mutation bugs.
    All fields must be set at construction time.
    """

    name: str  # Profile identifier
    description: str | None = None  # Human-readable description
    default_policy: Path | None = None  # Default policy file

    # Override sections (optional, merged with base config)
    tools: ToolPathsConfig | None = None
    behavior: BehaviorConfig | None = None
    logging: LoggingConfig | None = None
    jobs: JobsConfig | None = None


@dataclass
class TranscriptionPluginConfig:
    """Configuration for transcription plugins."""

    # Plugin to use (None = auto-detect)
    plugin: str | None = None

    # Whisper model size: tiny, base, small, medium, large
    model_size: str = "base"

    # Seconds to sample from audio (0 = full track)
    sample_duration: int = 30

    # Use GPU if available
    gpu_enabled: bool = True

    # Multi-sample detection settings
    max_samples: int = 3
    """Maximum number of samples to take when detecting language."""

    confidence_threshold: float = 0.85
    """Confidence level to stop sampling early (0.0-1.0)."""

    incumbent_bonus: float = 0.15
    """Bonus vote weight for track's existing language tag."""

    def __post_init__(self) -> None:
        """Validate configuration."""
        valid_model_sizes = {"tiny", "base", "small", "medium", "large"}
        if self.model_size not in valid_model_sizes:
            raise ValueError(
                f"model_size must be one of {valid_model_sizes}, got {self.model_size}"
            )
        if self.sample_duration < 0:
            raise ValueError(
                f"sample_duration must be non-negative, got {self.sample_duration}"
            )
        if self.max_samples < 1:
            raise ValueError(f"max_samples must be at least 1, got {self.max_samples}")
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError(
                f"confidence_threshold must be between 0.0 and 1.0, "
                f"got {self.confidence_threshold}"
            )
        if self.incumbent_bonus < 0.0:
            raise ValueError(
                f"incumbent_bonus must be non-negative, got {self.incumbent_bonus}"
            )


@dataclass
class ServerConfig:
    """Configuration for daemon server mode (012-daemon-systemd-server).

    Controls bind address, port, and shutdown behavior for `vpo serve`.
    """

    bind: str = "127.0.0.1"
    """Network address to bind to. Default localhost for security."""

    port: int = 8321
    """Port number for HTTP server. Default 8321 (distinctive, avoids conflicts)."""

    shutdown_timeout: float = 30.0
    """Seconds to wait for graceful shutdown before cancelling tasks."""

    auth_token: str | None = None
    """Shared secret for HTTP Basic Auth. None or empty disables authentication."""

    def __post_init__(self) -> None:
        """Validate configuration."""
        if not 1 <= self.port <= 65535:
            raise ValueError(f"port must be 1-65535, got {self.port}")
        if self.shutdown_timeout <= 0:
            raise ValueError(
                f"shutdown_timeout must be positive, got {self.shutdown_timeout}"
            )


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
    transcription: TranscriptionPluginConfig = field(
        default_factory=TranscriptionPluginConfig
    )
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    language: LanguageConfig = field(default_factory=LanguageConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)

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
