"""Configuration profile management.

Profiles allow users to store named configurations for different libraries
(movies, TV, kids content, etc.) and apply them via --profile flag.
"""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from vpo.config.models import Profile, VPOConfig


# Module-level storage for active profile in daemon mode
_active_profile: Profile | None = None


def set_active_profile(profile: Profile | None) -> None:
    """Set the active profile for daemon mode.

    This is called during daemon startup to make the profile
    configuration available to service functions.

    Args:
        profile: Profile to set as active, or None to clear.
    """
    global _active_profile
    _active_profile = profile


def get_active_profile() -> Profile | None:
    """Get the currently active profile (daemon mode only).

    Returns:
        The active Profile if set, or None if no profile is active.
    """
    return _active_profile


class ProfileError(Exception):
    """Error loading or validating a profile."""

    pass


class ProfileNotFoundError(ProfileError):
    """Profile does not exist."""

    pass


def _validate_and_construct(
    section_name: str,
    dataclass_type: type,
    data: dict[str, Any],
    profile_name: str,
) -> Any:
    """Construct a dataclass with validation for unknown keys.

    Args:
        section_name: Name of the profile section (for error messages).
        dataclass_type: The dataclass type to construct.
        data: Dictionary of values to pass to the dataclass.
        profile_name: Name of the profile (for error messages).

    Returns:
        Instance of the dataclass.

    Raises:
        ProfileError: If unknown keys are present or construction fails.
    """
    expected_fields = {f.name for f in fields(dataclass_type)}
    unknown_keys = set(data.keys()) - expected_fields

    if unknown_keys:
        raise ProfileError(
            f"Unknown keys in '{section_name}' section of profile '{profile_name}': "
            f"{sorted(unknown_keys)}. Valid keys are: {sorted(expected_fields)}"
        )

    try:
        return dataclass_type(**data)
    except TypeError as e:
        raise ProfileError(
            f"Invalid '{section_name}' configuration in profile '{profile_name}': {e}"
        ) from e


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
    from vpo.config.models import (
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

    # Parse nested config sections first (Profile is frozen, so we must build all
    # values before constructing it)
    tools_config: ToolPathsConfig | None = None
    behavior_config: BehaviorConfig | None = None
    logging_config: LoggingConfig | None = None
    jobs_config: JobsConfig | None = None

    if "tools" in data:
        tools_config = _validate_and_construct(
            "tools", ToolPathsConfig, data["tools"], name
        )
    if "behavior" in data:
        behavior_config = _validate_and_construct(
            "behavior", BehaviorConfig, data["behavior"], name
        )
    if "logging" in data:
        logging_data = data["logging"].copy()
        if "file" in logging_data:
            logging_data["file"] = Path(logging_data["file"]).expanduser()
        logging_config = _validate_and_construct(
            "logging", LoggingConfig, logging_data, name
        )
    if "jobs" in data:
        jobs_config = _validate_and_construct("jobs", JobsConfig, data["jobs"], name)

    # Build immutable Profile with all values at once
    return Profile(
        name=data.get("name", name),
        description=data.get("description"),
        default_policy=Path(data["default_policy"]).expanduser()
        if data.get("default_policy")
        else None,
        tools=tools_config,
        behavior=behavior_config,
        logging=logging_config,
        jobs=jobs_config,
    )


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
    from dataclasses import replace

    # Collect overrides from profile
    overrides: dict[str, Any] = {}

    if profile.tools:
        overrides["tools"] = profile.tools
    if profile.behavior:
        overrides["behavior"] = profile.behavior
    if profile.logging:
        overrides["logging"] = profile.logging
    if profile.jobs:
        overrides["jobs"] = profile.jobs

    # Always return new config instance (replace creates a copy)
    return replace(config, **overrides)
