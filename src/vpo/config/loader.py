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
- VPO_AUTH_TOKEN: Shared secret for HTTP Basic Auth (if set, protects web UI)
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from vpo.config.builder import (
    ConfigBuilder,
    ConfigSource,
    source_from_env,
    source_from_file,
)
from vpo.config.env import EnvReader
from vpo.config.models import VPOConfig
from vpo.config.toml_parser import load_toml_file

logger = logging.getLogger(__name__)

# Default config location
DEFAULT_CONFIG_DIR = Path.home() / ".vpo"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.toml"
DEFAULT_PLUGINS_DIR = DEFAULT_CONFIG_DIR / "plugins"

# Cache for loaded config files (path -> (parsed dict, mtime))
# This prevents redundant file reads and automatically reloads on file change
_config_cache: dict[Path, tuple[dict, float]] = {}
_config_cache_lock = threading.Lock()


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
    Supports tilde expansion (e.g., ~/custom/vpo).

    Returns:
        Path to the data directory (~/.vpo/ by default).
    """
    env_path = os.environ.get("VPO_DATA_DIR")
    if env_path:
        return Path(env_path).expanduser()
    return DEFAULT_CONFIG_DIR


def get_temp_directory() -> Path:
    """Get the temporary directory for intermediate files.

    Precedence (highest to lowest):
    1. VPO_TEMP_DIR environment variable
    2. Config file [jobs] temp_directory
    3. System default (tempfile.gettempdir())

    Use /dev/shm on Linux for RAM-backed storage.

    Returns:
        Path to the temp directory.
    """
    import tempfile

    # Check environment variable first
    env_path = os.environ.get("VPO_TEMP_DIR")
    if env_path:
        path = Path(env_path).expanduser().resolve()
        if path.exists() and path.is_dir():
            return path
        else:
            logger.warning(
                "VPO_TEMP_DIR '%s' is not a valid directory, "
                "falling back to config/default",
                env_path,
            )

    # Check config file (under [jobs] section)
    config = get_config()
    if config.jobs.temp_directory is not None:
        return config.jobs.temp_directory

    # Fall back to system default
    return Path(tempfile.gettempdir())


def load_config_file(path: Path | None = None) -> dict:
    """Load configuration from TOML file.

    Results are cached with mtime-based invalidation. The cache automatically
    reloads the file if it has been modified since the last read.
    Use clear_config_cache() to force a reload regardless of mtime.

    Thread-safe: uses a lock to protect concurrent access to the cache.

    Args:
        path: Path to config file. If None, uses default location.

    Returns:
        Parsed configuration dict. Empty dict if file doesn't exist.
    """
    if path is None:
        path = get_default_config_path()

    # Get current mtime (or 0.0 if file doesn't exist)
    try:
        current_mtime = path.stat().st_mtime
    except FileNotFoundError:
        current_mtime = 0.0

    # Fast path: check cache without lock (dict reads are atomic in CPython)
    if path in _config_cache:
        cached_config, cached_mtime = _config_cache[path]
        if current_mtime == cached_mtime:
            return cached_config

    # Slow path: acquire lock, double-check, then load
    with _config_cache_lock:
        # Double-check after acquiring lock (another thread may have loaded it)
        if path in _config_cache:
            cached_config, cached_mtime = _config_cache[path]
            if current_mtime == cached_mtime:
                return cached_config

        # Load and cache with mtime
        result = load_toml_file(path)
        _config_cache[path] = (result, current_mtime)
        return result


def clear_config_cache() -> None:
    """Clear the config file cache.

    Call this if the config file may have changed and you need
    a fresh load. Primarily useful for testing.

    Thread-safe: uses a lock to protect concurrent access to the cache.
    """
    with _config_cache_lock:
        _config_cache.clear()


def get_config(
    config_path: Path | None = None,
    # CLI overrides (highest precedence)
    ffmpeg_path: Path | None = None,
    ffprobe_path: Path | None = None,
    mkvmerge_path: Path | None = None,
    mkvpropedit_path: Path | None = None,
    database_path: Path | None = None,
    # Optional dependency injection for testing
    env_reader: EnvReader | None = None,
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
        env_reader: Optional EnvReader for testing (uses os.environ if None).

    Returns:
        VPOConfig with merged configuration.
    """
    # Use injected reader or create default
    reader = env_reader or EnvReader()

    # Load config file
    file_config = load_config_file(config_path)

    # Create sources
    file_source = source_from_file(file_config)
    env_source = source_from_env(reader)
    cli_source = ConfigSource(
        ffmpeg_path=ffmpeg_path,
        ffprobe_path=ffprobe_path,
        mkvmerge_path=mkvmerge_path,
        mkvpropedit_path=mkvpropedit_path,
        database_path=database_path,
    )

    # Build with precedence: file < env < cli
    builder = ConfigBuilder()
    builder.apply(file_source)
    builder.apply(env_source)
    builder.apply(cli_source)

    # Handle plugin directories specially (they have merge semantics)
    # Parse plugin directories from config file
    plugins_file = file_config.get("plugins", {})
    plugin_dirs_from_file: list[Path] = []
    if plugins_file.get("plugin_dirs"):
        for dir_str in plugins_file["plugin_dirs"]:
            plugin_dirs_from_file.append(Path(dir_str).expanduser())
    builder.set_plugin_dirs_from_file(plugin_dirs_from_file)

    # Parse plugin directories from environment variable (colon-separated)
    plugin_dirs_from_env = reader.get_path_list("VPO_PLUGIN_DIRS")
    if plugin_dirs_from_env:
        builder.set_plugin_dirs_from_env(plugin_dirs_from_env)

    return builder.build(default_plugins_dir=DEFAULT_PLUGINS_DIR)


# Legacy functions kept for backward compatibility
# These are deprecated and will be removed in a future version


def _parse_toml(content: str) -> dict:
    """Parse TOML content into a dict.

    DEPRECATED: Use vpo.config.toml_parser.parse_toml instead.
    """
    from vpo.config.toml_parser import parse_toml

    return parse_toml(content)


def _simple_toml_parse(content: str) -> dict:
    """Simple TOML parser for basic key=value configs.

    DEPRECATED: Use config.toml_parser.BasicTomlParser instead.
    """
    from vpo.config.toml_parser import BasicTomlParser

    return BasicTomlParser().parse(content)


def _get_env_path(var_name: str) -> Path | None:
    """Get a path from environment variable.

    DEPRECATED: Use EnvReader.get_path instead.
    """
    return EnvReader().get_path(var_name)


def _get_env_bool(var_name: str, default: bool) -> bool:
    """Get a boolean from environment variable.

    DEPRECATED: Use EnvReader.get_bool instead.
    """
    result = EnvReader().get_bool(var_name, default)
    return result if result is not None else default


def _get_env_int(var_name: str, default: int) -> int:
    """Get an integer from environment variable.

    DEPRECATED: Use EnvReader.get_int instead.
    """
    result = EnvReader().get_int(var_name, default)
    return result if result is not None else default


def _get_env_float(var_name: str, default: float) -> float:
    """Get a float from environment variable.

    DEPRECATED: Use EnvReader.get_float instead.
    """
    result = EnvReader().get_float(var_name, default)
    return result if result is not None else default


def _get_env_str(var_name: str, default: str) -> str:
    """Get a string from environment variable.

    DEPRECATED: Use EnvReader.get_str instead.
    """
    result = EnvReader().get_str(var_name, default)
    return result if result is not None else default
