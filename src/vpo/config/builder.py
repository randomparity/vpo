"""Configuration builder with explicit layering.

This module provides ConfigBuilder for building VPOConfig by composing
multiple configuration sources with explicit precedence handling.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from vpo.config.env import EnvReader
from vpo.config.models import (
    BehaviorConfig,
    DetectionConfig,
    JobsConfig,
    LanguageConfig,
    LoggingConfig,
    PluginConfig,
    ProcessingConfig,
    ServerConfig,
    ToolPathsConfig,
    TranscriptionPluginConfig,
    VPOConfig,
    WorkerConfig,
)


@dataclass
class ConfigSource:
    """Configuration values from a single source.

    None values indicate "not specified in this source" and will not
    override values from lower-precedence sources.

    This dataclass holds all possible configuration values that can
    come from CLI arguments, environment variables, or config files.
    """

    # Tool paths
    ffmpeg_path: Path | None = None
    ffprobe_path: Path | None = None
    mkvmerge_path: Path | None = None
    mkvpropedit_path: Path | None = None

    # Database
    database_path: Path | None = None

    # Detection config
    cache_ttl_hours: int | None = None
    auto_detect_on_startup: bool | None = None

    # Behavior config
    warn_on_missing_features: bool | None = None
    show_upgrade_suggestions: bool | None = None

    # Plugin config
    plugin_dirs: list[Path] | None = None
    entry_point_group: str | None = None
    plugin_auto_load: bool | None = None
    plugin_warn_unacknowledged: bool | None = None

    # Jobs config
    jobs_retention_days: int | None = None
    jobs_auto_purge: bool | None = None
    jobs_temp_directory: Path | None = None
    jobs_backup_original: bool | None = None
    jobs_log_compression_days: int | None = None
    jobs_log_deletion_days: int | None = None

    # Worker config
    worker_max_files: int | None = None
    worker_max_duration: int | None = None
    worker_end_by: str | None = None
    worker_cpu_cores: int | None = None

    # Server config
    server_bind: str | None = None
    server_port: int | None = None
    server_shutdown_timeout: float | None = None
    server_auth_token: str | None = None

    # Language config
    language_standard: str | None = None
    language_warn_on_conversion: bool | None = None

    # Logging config
    logging_level: str | None = None
    logging_file: Path | None = None
    logging_format: str | None = None
    logging_include_stderr: bool | None = None
    logging_max_bytes: int | None = None
    logging_backup_count: int | None = None

    # Transcription config
    transcription_plugin: str | None = None
    transcription_model_size: str | None = None
    transcription_sample_duration: int | None = None
    transcription_gpu_enabled: bool | None = None
    transcription_max_samples: int | None = None
    transcription_confidence_threshold: float | None = None
    transcription_incumbent_bonus: float | None = None

    # Processing config
    processing_workers: int | None = None


class ConfigBuilder:
    """Builds VPOConfig by layering ConfigSources with precedence.

    The builder accumulates configuration values from multiple sources.
    Later sources override earlier ones (for non-None values).

    Example:
        builder = ConfigBuilder()
        builder.apply(source_from_file(file_config))
        builder.apply(source_from_env(reader))
        builder.apply(cli_source)
        config = builder.build(default_plugins_dir)
    """

    def __init__(self) -> None:
        """Initialize the builder with no values set."""
        self._values: dict[str, Any] = {}
        self._plugin_dirs_from_file: list[Path] = []
        self._plugin_dirs_from_env: list[Path] = []

    # Fields with special handling (merge instead of override)
    _SPECIAL_FIELDS = frozenset({"plugin_dirs"})

    def apply(self, source: ConfigSource) -> None:
        """Apply configuration source, overriding existing values.

        Non-None values from the source override existing values.
        None values are ignored (preserve existing).

        Args:
            source: Configuration source to apply.
        """
        # Iterate through all fields using dataclasses introspection
        for field_obj in fields(source):
            # Skip fields with special handling
            if field_obj.name in self._SPECIAL_FIELDS:
                continue

            value = getattr(source, field_obj.name)
            if value is not None:
                self._values[field_obj.name] = value

        # Plugin dirs handled specially (they merge, not override)
        # Tracked via set_plugin_dirs_from_file/env methods

    def set_plugin_dirs_from_file(self, dirs: list[Path]) -> None:
        """Set plugin directories from config file.

        Args:
            dirs: List of plugin directories from config file.
        """
        self._plugin_dirs_from_file = dirs

    def set_plugin_dirs_from_env(self, dirs: list[Path]) -> None:
        """Set plugin directories from environment variable.

        Args:
            dirs: List of plugin directories from environment.
        """
        self._plugin_dirs_from_env = dirs

    def _get(self, key: str, default: Any) -> Any:
        """Get a value with fallback to default.

        Args:
            key: Configuration key.
            default: Default value if not set.

        Returns:
            The configured value or default.
        """
        return self._values.get(key, default)

    def build(self, default_plugins_dir: Path) -> VPOConfig:
        """Build the final VPOConfig with defaults for unset values.

        Args:
            default_plugins_dir: Default plugins directory to include.

        Returns:
            Complete VPOConfig with all values resolved.
        """
        # Build tool paths
        tools = ToolPathsConfig(
            ffmpeg=self._get("ffmpeg_path", None),
            ffprobe=self._get("ffprobe_path", None),
            mkvmerge=self._get("mkvmerge_path", None),
            mkvpropedit=self._get("mkvpropedit_path", None),
        )

        # Build detection config
        detection = DetectionConfig(
            cache_ttl_hours=self._get("cache_ttl_hours", 24),
            auto_detect_on_startup=self._get("auto_detect_on_startup", True),
        )

        # Build behavior config
        behavior = BehaviorConfig(
            warn_on_missing_features=self._get("warn_on_missing_features", True),
            show_upgrade_suggestions=self._get("show_upgrade_suggestions", True),
        )

        # Build plugin config with directory merging
        # Env takes precedence over file, default always included
        plugin_dirs = self._plugin_dirs_from_env or self._plugin_dirs_from_file
        if default_plugins_dir not in plugin_dirs:
            plugin_dirs = plugin_dirs + [default_plugins_dir]

        plugins = PluginConfig(
            plugin_dirs=plugin_dirs,
            entry_point_group=self._get("entry_point_group", "vpo.plugins"),
            auto_load=self._get("plugin_auto_load", True),
            warn_unacknowledged=self._get("plugin_warn_unacknowledged", True),
        )

        # Build jobs config
        jobs = JobsConfig(
            retention_days=self._get("jobs_retention_days", 30),
            auto_purge=self._get("jobs_auto_purge", True),
            temp_directory=self._get("jobs_temp_directory", None),
            backup_original=self._get("jobs_backup_original", True),
            log_compression_days=self._get("jobs_log_compression_days", 7),
            log_deletion_days=self._get("jobs_log_deletion_days", 90),
        )

        # Build worker config
        # Note: 0 means "no limit", convert to None
        worker_max_files = self._get("worker_max_files", None)
        worker_max_duration = self._get("worker_max_duration", None)
        worker_cpu_cores = self._get("worker_cpu_cores", None)

        worker = WorkerConfig(
            max_files=worker_max_files if worker_max_files else None,
            max_duration=worker_max_duration if worker_max_duration else None,
            end_by=self._get("worker_end_by", None),
            cpu_cores=worker_cpu_cores if worker_cpu_cores else None,
        )

        # Build server config
        server = ServerConfig(
            bind=self._get("server_bind", "127.0.0.1"),
            port=self._get("server_port", 8321),
            shutdown_timeout=self._get("server_shutdown_timeout", 30.0),
            auth_token=self._get("server_auth_token", None),
        )

        # Build language config
        language = LanguageConfig(
            standard=self._get("language_standard", "639-2/B"),
            warn_on_conversion=self._get("language_warn_on_conversion", True),
        )

        # Build logging config
        logging_config = LoggingConfig(
            level=self._get("logging_level", "info"),
            file=self._get("logging_file", None),
            format=self._get("logging_format", "text"),
            include_stderr=self._get("logging_include_stderr", False),
            max_bytes=self._get("logging_max_bytes", 10_485_760),
            backup_count=self._get("logging_backup_count", 5),
        )

        # Build transcription config
        transcription = TranscriptionPluginConfig(
            plugin=self._get("transcription_plugin", None),
            model_size=self._get("transcription_model_size", "base"),
            sample_duration=self._get("transcription_sample_duration", 30),
            gpu_enabled=self._get("transcription_gpu_enabled", True),
            max_samples=self._get("transcription_max_samples", 3),
            confidence_threshold=self._get("transcription_confidence_threshold", 0.85),
            incumbent_bonus=self._get("transcription_incumbent_bonus", 0.15),
        )

        # Build processing config
        processing = ProcessingConfig(
            workers=self._get("processing_workers", 2),
        )

        return VPOConfig(
            tools=tools,
            detection=detection,
            behavior=behavior,
            plugins=plugins,
            jobs=jobs,
            worker=worker,
            transcription=transcription,
            logging=logging_config,
            server=server,
            language=language,
            processing=processing,
            database_path=self._get("database_path", None),
        )


def source_from_file(file_config: dict[str, Any]) -> ConfigSource:
    """Create ConfigSource from parsed TOML config file.

    Args:
        file_config: Parsed configuration dictionary from TOML file.

    Returns:
        ConfigSource with values from the config file.
    """
    tools = file_config.get("tools", {})
    detection = tools.get("detection", {})
    behavior = file_config.get("behavior", {})
    plugins = file_config.get("plugins", {})
    jobs = file_config.get("jobs", {})
    worker = file_config.get("worker", {})
    server = file_config.get("server", {})
    language = file_config.get("language", {})
    logging_conf = file_config.get("logging", {})
    transcription = file_config.get("transcription", {})
    processing = file_config.get("processing", {})

    # Parse plugin directories
    plugin_dirs: list[Path] | None = None
    if plugins.get("plugin_dirs"):
        plugin_dirs = [Path(d).expanduser() for d in plugins["plugin_dirs"]]

    # Parse temp directory
    temp_dir_str = jobs.get("temp_directory")
    temp_dir = Path(temp_dir_str).expanduser() if temp_dir_str else None

    # Parse log file
    log_file_str = logging_conf.get("file")
    log_file = Path(log_file_str).expanduser() if log_file_str else None

    return ConfigSource(
        # Tool paths
        ffmpeg_path=Path(tools["ffmpeg"]) if tools.get("ffmpeg") else None,
        ffprobe_path=Path(tools["ffprobe"]) if tools.get("ffprobe") else None,
        mkvmerge_path=Path(tools["mkvmerge"]) if tools.get("mkvmerge") else None,
        mkvpropedit_path=(
            Path(tools["mkvpropedit"]) if tools.get("mkvpropedit") else None
        ),
        # Database
        database_path=(
            Path(file_config["database_path"])
            if file_config.get("database_path")
            else None
        ),
        # Detection
        cache_ttl_hours=detection.get("cache_ttl_hours"),
        auto_detect_on_startup=detection.get("auto_detect_on_startup"),
        # Behavior
        warn_on_missing_features=behavior.get("warn_on_missing_features"),
        show_upgrade_suggestions=behavior.get("show_upgrade_suggestions"),
        # Plugins
        plugin_dirs=plugin_dirs,
        entry_point_group=plugins.get("entry_point_group"),
        plugin_auto_load=plugins.get("auto_load"),
        plugin_warn_unacknowledged=plugins.get("warn_unacknowledged"),
        # Jobs
        jobs_retention_days=jobs.get("retention_days"),
        jobs_auto_purge=jobs.get("auto_purge"),
        jobs_temp_directory=temp_dir,
        jobs_backup_original=jobs.get("backup_original"),
        jobs_log_compression_days=jobs.get("log_compression_days"),
        jobs_log_deletion_days=jobs.get("log_deletion_days"),
        # Worker
        worker_max_files=worker.get("max_files"),
        worker_max_duration=worker.get("max_duration"),
        worker_end_by=worker.get("end_by"),
        worker_cpu_cores=worker.get("cpu_cores"),
        # Server
        server_bind=server.get("bind"),
        server_port=server.get("port"),
        server_shutdown_timeout=server.get("shutdown_timeout"),
        server_auth_token=server.get("auth_token"),
        # Language
        language_standard=language.get("standard"),
        language_warn_on_conversion=language.get("warn_on_conversion"),
        # Logging
        logging_level=logging_conf.get("level"),
        logging_file=log_file,
        logging_format=logging_conf.get("format"),
        logging_include_stderr=logging_conf.get("include_stderr"),
        logging_max_bytes=logging_conf.get("max_bytes"),
        logging_backup_count=logging_conf.get("backup_count"),
        # Transcription
        transcription_plugin=transcription.get("plugin"),
        transcription_model_size=transcription.get("model_size"),
        transcription_sample_duration=transcription.get("sample_duration"),
        transcription_gpu_enabled=transcription.get("gpu_enabled"),
        transcription_max_samples=transcription.get("max_samples"),
        transcription_confidence_threshold=transcription.get("confidence_threshold"),
        transcription_incumbent_bonus=transcription.get("incumbent_bonus"),
        # Processing
        processing_workers=processing.get("workers"),
    )


def source_from_env(reader: EnvReader) -> ConfigSource:
    """Create ConfigSource from environment variables.

    Args:
        reader: EnvReader instance for reading environment variables.

    Returns:
        ConfigSource with values from environment variables.
    """
    return ConfigSource(
        # Tool paths
        ffmpeg_path=reader.get_path("VPO_FFMPEG_PATH"),
        ffprobe_path=reader.get_path("VPO_FFPROBE_PATH"),
        mkvmerge_path=reader.get_path("VPO_MKVMERGE_PATH"),
        mkvpropedit_path=reader.get_path("VPO_MKVPROPEDIT_PATH"),
        # Database
        database_path=reader.get_path("VPO_DATABASE_PATH"),
        # Detection
        cache_ttl_hours=reader.get_int("VPO_CACHE_TTL_HOURS"),
        auto_detect_on_startup=reader.get_bool("VPO_AUTO_DETECT_ON_STARTUP"),
        # Behavior
        warn_on_missing_features=reader.get_bool("VPO_WARN_ON_MISSING_FEATURES"),
        show_upgrade_suggestions=reader.get_bool("VPO_SHOW_UPGRADE_SUGGESTIONS"),
        # Plugins (dirs handled separately)
        plugin_dirs=None,  # Handled by set_plugin_dirs_from_env
        entry_point_group=None,  # No env var
        plugin_auto_load=reader.get_bool("VPO_PLUGIN_AUTO_LOAD"),
        plugin_warn_unacknowledged=reader.get_bool("VPO_PLUGIN_WARN_UNACKNOWLEDGED"),
        # Jobs
        jobs_retention_days=reader.get_int("VPO_JOBS_RETENTION_DAYS"),
        jobs_auto_purge=reader.get_bool("VPO_JOBS_AUTO_PURGE"),
        jobs_temp_directory=None,  # No env var for temp dir
        jobs_backup_original=reader.get_bool("VPO_JOBS_BACKUP_ORIGINAL"),
        jobs_log_compression_days=reader.get_int("VPO_LOG_COMPRESSION_DAYS"),
        jobs_log_deletion_days=reader.get_int("VPO_LOG_DELETION_DAYS"),
        # Worker
        worker_max_files=reader.get_int("VPO_WORKER_MAX_FILES"),
        worker_max_duration=reader.get_int("VPO_WORKER_MAX_DURATION"),
        worker_end_by=reader.get_str("VPO_WORKER_END_BY"),
        worker_cpu_cores=reader.get_int("VPO_WORKER_CPU_CORES"),
        # Server
        server_bind=reader.get_str("VPO_SERVER_BIND"),
        server_port=reader.get_int("VPO_SERVER_PORT"),
        server_shutdown_timeout=reader.get_float("VPO_SERVER_SHUTDOWN_TIMEOUT"),
        server_auth_token=reader.get_str("VPO_AUTH_TOKEN"),
        # Language
        language_standard=reader.get_str("VPO_LANGUAGE_STANDARD"),
        language_warn_on_conversion=reader.get_bool("VPO_LANGUAGE_WARN_ON_CONVERSION"),
        # Logging (no env vars defined for logging currently)
        logging_level=None,
        logging_file=None,
        logging_format=None,
        logging_include_stderr=None,
        logging_max_bytes=None,
        logging_backup_count=None,
        # Transcription
        transcription_plugin=reader.get_str("VPO_TRANSCRIPTION_PLUGIN"),
        transcription_model_size=reader.get_str("VPO_TRANSCRIPTION_MODEL_SIZE"),
        transcription_sample_duration=reader.get_int(
            "VPO_TRANSCRIPTION_SAMPLE_DURATION"
        ),
        transcription_gpu_enabled=reader.get_bool("VPO_TRANSCRIPTION_GPU_ENABLED"),
        transcription_max_samples=reader.get_int("VPO_TRANSCRIPTION_MAX_SAMPLES"),
        transcription_confidence_threshold=reader.get_float(
            "VPO_TRANSCRIPTION_CONFIDENCE_THRESHOLD"
        ),
        transcription_incumbent_bonus=reader.get_float(
            "VPO_TRANSCRIPTION_INCUMBENT_BONUS"
        ),
        # Processing
        processing_workers=reader.get_int("VPO_PROCESSING_WORKERS"),
    )
