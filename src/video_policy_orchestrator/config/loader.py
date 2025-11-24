"""Configuration loader with precedence handling.

Configuration is loaded with the following precedence (highest to lowest):
1. CLI arguments (passed directly to functions)
2. Environment variables (VPO_*)
3. Config file (~/.vpo/config.toml)
4. Default values

Environment variables:
- VPO_FFMPEG_PATH: Path to ffmpeg executable
- VPO_FFPROBE_PATH: Path to ffprobe executable
- VPO_MKVMERGE_PATH: Path to mkvmerge executable
- VPO_MKVPROPEDIT_PATH: Path to mkvpropedit executable
- VPO_DATABASE_PATH: Path to database file
- VPO_CONFIG_PATH: Path to config file (overrides default location)
- VPO_DATA_DIR: Path to VPO data directory (overrides ~/.vpo/)
- VPO_LOG_COMPRESSION_DAYS: Days before compressing job logs (default 7)
- VPO_LOG_DELETION_DAYS: Days before deleting job logs (default 90)
"""

import logging
import os
from pathlib import Path

from video_policy_orchestrator.config.models import (
    BehaviorConfig,
    DetectionConfig,
    JobsConfig,
    LanguageConfig,
    PluginConfig,
    ServerConfig,
    ToolPathsConfig,
    VPOConfig,
    WorkerConfig,
)

logger = logging.getLogger(__name__)

# Default config location
DEFAULT_CONFIG_DIR = Path.home() / ".vpo"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.toml"
DEFAULT_PLUGINS_DIR = DEFAULT_CONFIG_DIR / "plugins"


def get_default_config_path() -> Path:
    """Get the default config file path.

    Can be overridden by VPO_CONFIG_PATH environment variable.

    Returns:
        Path to config file.
    """
    env_path = os.environ.get("VPO_CONFIG_PATH")
    if env_path:
        return Path(env_path)
    return DEFAULT_CONFIG_FILE


def get_data_dir() -> Path:
    """Get the VPO data directory.

    This is the base directory for all VPO data including:
    - Database file (library.db)
    - Configuration file (config.toml)
    - Plugins directory (plugins/)
    - Job logs directory (logs/)

    Can be overridden by VPO_DATA_DIR environment variable.

    Returns:
        Path to the data directory (~/.vpo/ by default).
    """
    env_path = os.environ.get("VPO_DATA_DIR")
    if env_path:
        return Path(env_path)
    return DEFAULT_CONFIG_DIR


def _parse_toml(content: str) -> dict:
    """Parse TOML content into a dict.

    Uses tomllib (Python 3.11+) or falls back to a simple parser.

    Args:
        content: TOML file content.

    Returns:
        Parsed dict.
    """
    try:
        import tomllib

        return tomllib.loads(content)
    except ImportError:
        # Fallback for Python < 3.11: try tomli
        try:
            import tomli

            return tomli.loads(content)
        except ImportError:
            # Last resort: simple key=value parser for basic configs
            return _simple_toml_parse(content)


def _simple_toml_parse(content: str) -> dict:
    """Simple TOML parser for basic key=value configs.

    Handles:
    - [section] headers
    - key = "value" pairs
    - Comments (#)

    Args:
        content: TOML content.

    Returns:
        Parsed dict.
    """
    result: dict = {}
    current_section: dict | None = None

    for line in content.split("\n"):
        line = line.strip()

        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        # Section header
        if line.startswith("[") and line.endswith("]"):
            section_path = line[1:-1].strip()
            parts = section_path.split(".")

            # Navigate/create nested sections
            current = result
            for part in parts:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current_section = current
            continue

        # Key = value
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()

            # Remove quotes from string values
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            # Parse booleans
            elif value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            # Parse integers
            elif value.isdigit():
                value = int(value)

            target = current_section if current_section is not None else result
            target[key] = value

    return result


def load_config_file(path: Path | None = None) -> dict:
    """Load configuration from TOML file.

    Args:
        path: Path to config file. If None, uses default location.

    Returns:
        Parsed configuration dict. Empty dict if file doesn't exist.
    """
    if path is None:
        path = get_default_config_path()

    if not path.exists():
        logger.debug("Config file not found: %s", path)
        return {}

    try:
        content = path.read_text()
        config = _parse_toml(content)
        logger.debug("Loaded config from %s", path)
        return config
    except Exception as e:
        logger.warning("Failed to load config file %s: %s", path, e)
        return {}


def _get_env_path(var_name: str) -> Path | None:
    """Get a path from environment variable.

    Args:
        var_name: Environment variable name.

    Returns:
        Path if set and valid, None otherwise.
    """
    value = os.environ.get(var_name)
    if value:
        path = Path(value)
        if path.exists():
            return path
        logger.warning(
            "Environment variable %s points to non-existent path: %s",
            var_name,
            value,
        )
    return None


def _get_env_bool(var_name: str, default: bool) -> bool:
    """Get a boolean from environment variable.

    Args:
        var_name: Environment variable name.
        default: Default value if not set.

    Returns:
        Boolean value.
    """
    value = os.environ.get(var_name)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def _get_env_int(var_name: str, default: int) -> int:
    """Get an integer from environment variable.

    Args:
        var_name: Environment variable name.
        default: Default value if not set.

    Returns:
        Integer value.
    """
    value = os.environ.get(var_name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning("Invalid integer value for %s: %s", var_name, value)
        return default


def _get_env_float(var_name: str, default: float) -> float:
    """Get a float from environment variable.

    Args:
        var_name: Environment variable name.
        default: Default value if not set.

    Returns:
        Float value.
    """
    value = os.environ.get(var_name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        logger.warning("Invalid float value for %s: %s", var_name, value)
        return default


def _get_env_str(var_name: str, default: str) -> str:
    """Get a string from environment variable.

    Args:
        var_name: Environment variable name.
        default: Default value if not set.

    Returns:
        String value.
    """
    return os.environ.get(var_name, default)


def get_config(
    config_path: Path | None = None,
    # CLI overrides (highest precedence)
    ffmpeg_path: Path | None = None,
    ffprobe_path: Path | None = None,
    mkvmerge_path: Path | None = None,
    mkvpropedit_path: Path | None = None,
    database_path: Path | None = None,
) -> VPOConfig:
    """Get VPO configuration with full precedence handling.

    Precedence (highest to lowest):
    1. CLI arguments passed to this function
    2. Environment variables (VPO_*)
    3. Config file
    4. Default values

    Args:
        config_path: Path to config file (overrides VPO_CONFIG_PATH).
        ffmpeg_path: CLI override for ffmpeg path.
        ffprobe_path: CLI override for ffprobe path.
        mkvmerge_path: CLI override for mkvmerge path.
        mkvpropedit_path: CLI override for mkvpropedit path.
        database_path: CLI override for database path.

    Returns:
        VPOConfig with merged configuration.
    """
    # Load config file
    file_config = load_config_file(config_path)

    # Build tool paths config
    tools_file = file_config.get("tools", {})
    tools = ToolPathsConfig(
        ffmpeg=(
            ffmpeg_path
            or _get_env_path("VPO_FFMPEG_PATH")
            or (Path(tools_file["ffmpeg"]) if tools_file.get("ffmpeg") else None)
        ),
        ffprobe=(
            ffprobe_path
            or _get_env_path("VPO_FFPROBE_PATH")
            or (Path(tools_file["ffprobe"]) if tools_file.get("ffprobe") else None)
        ),
        mkvmerge=(
            mkvmerge_path
            or _get_env_path("VPO_MKVMERGE_PATH")
            or (Path(tools_file["mkvmerge"]) if tools_file.get("mkvmerge") else None)
        ),
        mkvpropedit=(
            mkvpropedit_path
            or _get_env_path("VPO_MKVPROPEDIT_PATH")
            or (
                Path(tools_file["mkvpropedit"])
                if tools_file.get("mkvpropedit")
                else None
            )
        ),
    )

    # Build detection config
    detection_file = file_config.get("tools", {}).get("detection", {})
    detection = DetectionConfig(
        cache_ttl_hours=_get_env_int(
            "VPO_CACHE_TTL_HOURS",
            detection_file.get("cache_ttl_hours", 24),
        ),
        auto_detect_on_startup=_get_env_bool(
            "VPO_AUTO_DETECT_ON_STARTUP",
            detection_file.get("auto_detect_on_startup", True),
        ),
    )

    # Build behavior config
    behavior_file = file_config.get("behavior", {})
    behavior = BehaviorConfig(
        warn_on_missing_features=_get_env_bool(
            "VPO_WARN_ON_MISSING_FEATURES",
            behavior_file.get("warn_on_missing_features", True),
        ),
        show_upgrade_suggestions=_get_env_bool(
            "VPO_SHOW_UPGRADE_SUGGESTIONS",
            behavior_file.get("show_upgrade_suggestions", True),
        ),
    )

    # Build database path
    db_path = (
        database_path
        or _get_env_path("VPO_DATABASE_PATH")
        or (
            Path(file_config["database_path"])
            if file_config.get("database_path")
            else None
        )
    )

    # Build plugin config
    plugins_file = file_config.get("plugins", {})

    # Parse plugin directories from config file
    plugin_dirs_from_file: list[Path] = []
    if plugins_file.get("plugin_dirs"):
        for dir_str in plugins_file["plugin_dirs"]:
            plugin_dirs_from_file.append(Path(dir_str).expanduser())

    # Parse plugin directories from environment variable (colon-separated)
    plugin_dirs_from_env: list[Path] = []
    env_plugin_dirs = os.environ.get("VPO_PLUGIN_DIRS")
    if env_plugin_dirs:
        for dir_str in env_plugin_dirs.split(":"):
            if dir_str.strip():
                plugin_dirs_from_env.append(Path(dir_str.strip()).expanduser())

    # Merge directories: env takes precedence, then file, default always included
    all_plugin_dirs = plugin_dirs_from_env or plugin_dirs_from_file
    if DEFAULT_PLUGINS_DIR not in all_plugin_dirs:
        all_plugin_dirs.append(DEFAULT_PLUGINS_DIR)

    plugins = PluginConfig(
        plugin_dirs=all_plugin_dirs,
        entry_point_group=plugins_file.get("entry_point_group", "vpo.plugins"),
        auto_load=_get_env_bool(
            "VPO_PLUGIN_AUTO_LOAD",
            plugins_file.get("auto_load", True),
        ),
        warn_unacknowledged=_get_env_bool(
            "VPO_PLUGIN_WARN_UNACKNOWLEDGED",
            plugins_file.get("warn_unacknowledged", True),
        ),
    )

    # Build jobs config
    jobs_file = file_config.get("jobs", {})
    temp_dir_str = jobs_file.get("temp_directory")
    jobs = JobsConfig(
        retention_days=_get_env_int(
            "VPO_JOBS_RETENTION_DAYS",
            jobs_file.get("retention_days", 30),
        ),
        auto_purge=_get_env_bool(
            "VPO_JOBS_AUTO_PURGE",
            jobs_file.get("auto_purge", True),
        ),
        temp_directory=Path(temp_dir_str).expanduser() if temp_dir_str else None,
        backup_original=_get_env_bool(
            "VPO_JOBS_BACKUP_ORIGINAL",
            jobs_file.get("backup_original", True),
        ),
        log_compression_days=_get_env_int(
            "VPO_LOG_COMPRESSION_DAYS",
            jobs_file.get("log_compression_days", 7),
        ),
        log_deletion_days=_get_env_int(
            "VPO_LOG_DELETION_DAYS",
            jobs_file.get("log_deletion_days", 90),
        ),
    )

    # Build worker config
    worker_file = file_config.get("worker", {})
    worker = WorkerConfig(
        max_files=_get_env_int(
            "VPO_WORKER_MAX_FILES",
            worker_file.get("max_files", 0),
        )
        or None,
        max_duration=_get_env_int(
            "VPO_WORKER_MAX_DURATION",
            worker_file.get("max_duration", 0),
        )
        or None,
        end_by=os.environ.get("VPO_WORKER_END_BY") or worker_file.get("end_by"),
        cpu_cores=_get_env_int(
            "VPO_WORKER_CPU_CORES",
            worker_file.get("cpu_cores", 0),
        )
        or None,
    )

    # Build server config
    server_file = file_config.get("server", {})
    server = ServerConfig(
        bind=_get_env_str(
            "VPO_SERVER_BIND",
            server_file.get("bind", "127.0.0.1"),
        ),
        port=_get_env_int(
            "VPO_SERVER_PORT",
            server_file.get("port", 8321),
        ),
        shutdown_timeout=_get_env_float(
            "VPO_SERVER_SHUTDOWN_TIMEOUT",
            server_file.get("shutdown_timeout", 30.0),
        ),
    )

    # Build language config
    language_file = file_config.get("language", {})
    language = LanguageConfig(
        standard=_get_env_str(
            "VPO_LANGUAGE_STANDARD",
            language_file.get("standard", "639-2/B"),
        ),  # type: ignore[arg-type]
        warn_on_conversion=_get_env_bool(
            "VPO_LANGUAGE_WARN_ON_CONVERSION",
            language_file.get("warn_on_conversion", True),
        ),
    )

    return VPOConfig(
        tools=tools,
        detection=detection,
        behavior=behavior,
        plugins=plugins,
        jobs=jobs,
        worker=worker,
        server=server,
        language=language,
        database_path=db_path,
    )
