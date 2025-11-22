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
"""

import logging
import os
from pathlib import Path

from video_policy_orchestrator.config.models import (
    BehaviorConfig,
    DetectionConfig,
    ToolPathsConfig,
    VPOConfig,
)

logger = logging.getLogger(__name__)

# Default config location
DEFAULT_CONFIG_DIR = Path.home() / ".vpo"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.toml"


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

    return VPOConfig(
        tools=tools,
        detection=detection,
        behavior=behavior,
        database_path=db_path,
    )
