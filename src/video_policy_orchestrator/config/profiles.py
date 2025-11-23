"""Configuration profile management.

Profiles allow users to store named configurations for different libraries
(movies, TV, kids content, etc.) and apply them via --profile flag.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from video_policy_orchestrator.config.models import Profile, VPOConfig


class ProfileError(Exception):
    """Error loading or validating a profile."""

    pass


class ProfileNotFoundError(ProfileError):
    """Profile does not exist."""

    pass


def get_profiles_directory() -> Path:
    """Get the profiles directory path.

    Returns:
        Path to ~/.vpo/profiles/
    """
    return Path.home() / ".vpo" / "profiles"


def list_profiles() -> list[str]:
    """List available profile names.

    Returns:
        List of profile names (without .yaml extension).
    """
    profiles_dir = get_profiles_directory()
    if not profiles_dir.exists():
        return []

    return [
        p.stem
        for p in profiles_dir.glob("*.yaml")
        if p.is_file() and not p.name.startswith(".")
    ]


def load_profile(name: str) -> Profile:
    """Load a profile by name.

    Args:
        name: Profile name (without .yaml extension).

    Returns:
        Loaded Profile dataclass.

    Raises:
        ProfileNotFoundError: If profile doesn't exist.
        ProfileError: If profile is invalid.
    """
    # Import here to avoid circular imports
    from video_policy_orchestrator.config.models import (
        BehaviorConfig,
        JobsConfig,
        LoggingConfig,
        Profile,
        ToolPathsConfig,
    )

    # Validate name
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        raise ProfileError(f"Profile name must be alphanumeric (with - or _): {name}")

    profiles_dir = get_profiles_directory()
    profile_path = profiles_dir / f"{name}.yaml"

    if not profile_path.exists():
        raise ProfileNotFoundError(f"Profile not found: {name}")

    try:
        with open(profile_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ProfileError(f"Invalid YAML in profile {name}: {e}") from e

    # Build Profile from YAML data
    profile = Profile(
        name=data.get("name", name),
        description=data.get("description"),
        default_policy=Path(data["default_policy"]).expanduser()
        if data.get("default_policy")
        else None,
    )

    # Parse nested config sections if present
    if "tools" in data:
        profile.tools = ToolPathsConfig(**data["tools"])
    if "behavior" in data:
        profile.behavior = BehaviorConfig(**data["behavior"])
    if "logging" in data:
        logging_data = data["logging"].copy()
        if "file" in logging_data:
            logging_data["file"] = Path(logging_data["file"]).expanduser()
        profile.logging = LoggingConfig(**logging_data)
    if "jobs" in data:
        profile.jobs = JobsConfig(**data["jobs"])

    return profile


def validate_profile(profile: Profile) -> list[str]:
    """Validate a profile configuration.

    Args:
        profile: Profile to validate.

    Returns:
        List of validation error messages (empty if valid).
    """
    errors = []

    # Check default_policy exists if specified
    if profile.default_policy and not profile.default_policy.exists():
        errors.append(f"Policy file not found: {profile.default_policy}")

    # Check logging file directory exists if specified
    if profile.logging and profile.logging.file:
        log_dir = profile.logging.file.parent
        if not log_dir.exists():
            errors.append(f"Log directory does not exist: {log_dir}")

    return errors


def merge_profile_with_config(profile: Profile, config: VPOConfig) -> VPOConfig:
    """Merge profile settings into a base config.

    Profile settings override base config. CLI flags (applied later) override profile.

    Precedence (highest wins):
        1. CLI flags
        2. Profile settings
        3. Base config
        4. Defaults

    Args:
        profile: Profile to apply.
        config: Base configuration.

    Returns:
        New VPOConfig with profile settings merged in.
    """
    # Import here to avoid circular imports
    from dataclasses import replace

    # Start with a copy of the base config
    merged = replace(config)

    # Override sections that are specified in the profile
    if profile.tools:
        merged.tools = profile.tools
    if profile.behavior:
        merged.behavior = profile.behavior
    if profile.logging:
        merged.logging = profile.logging
    if profile.jobs:
        merged.jobs = profile.jobs

    return merged
