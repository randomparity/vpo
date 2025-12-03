"""Configuration management for Video Policy Orchestrator.

This module provides configuration loading with precedence handling:
1. CLI flags (highest priority)
2. Environment variables (VPO_*)
3. Config file (~/.vpo/config.toml)
4. Default values (lowest priority)

New architecture (introduced in refactor):
- EnvReader: Testable environment variable reading with DI support
- ConfigBuilder: Layered config construction with explicit precedence
- build_logging_config: Factory for merging CLI overrides with base config
- parse_toml/load_toml_file: Isolated TOML parsing
"""

from video_policy_orchestrator.config.builder import (
    ConfigBuilder,
    ConfigSource,
    source_from_env,
    source_from_file,
)
from video_policy_orchestrator.config.env import EnvReader
from video_policy_orchestrator.config.loader import (
    clear_config_cache,
    get_config,
    get_default_config_path,
    get_temp_directory,
    load_config_file,
)
from video_policy_orchestrator.config.logging_factory import (
    build_logging_config,
    configure_logging_from_cli,
)
from video_policy_orchestrator.config.models import (
    BehaviorConfig,
    DetectionConfig,
    ToolPathsConfig,
    VPOConfig,
)
from video_policy_orchestrator.config.toml_parser import (
    BasicTomlParser,
    TomlParseError,
    load_toml_file,
    parse_toml,
)

__all__ = [
    # Models
    "BehaviorConfig",
    "DetectionConfig",
    "ToolPathsConfig",
    "VPOConfig",
    # Loader
    "clear_config_cache",
    "get_config",
    "get_default_config_path",
    "get_temp_directory",
    "load_config_file",
    # New modules (refactored architecture)
    "EnvReader",
    "ConfigBuilder",
    "ConfigSource",
    "source_from_env",
    "source_from_file",
    "build_logging_config",
    "configure_logging_from_cli",
    "parse_toml",
    "load_toml_file",
    "BasicTomlParser",
    "TomlParseError",
]
