"""Configuration management for Video Policy Orchestrator.

This module provides configuration loading with precedence handling:
1. CLI flags (highest priority)
2. Environment variables (VPO_*)
3. Config file (~/.vpo/config.toml)
4. Default values (lowest priority)
"""

from video_policy_orchestrator.config.loader import (
    get_config,
    get_default_config_path,
    load_config_file,
)
from video_policy_orchestrator.config.models import (
    BehaviorConfig,
    DetectionConfig,
    ToolPathsConfig,
    VPOConfig,
)

__all__ = [
    # Models
    "BehaviorConfig",
    "DetectionConfig",
    "ToolPathsConfig",
    "VPOConfig",
    # Loader
    "get_config",
    "load_config_file",
    "get_default_config_path",
]
