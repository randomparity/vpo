"""Shared profile loading with consistent error handling.

This module provides a unified profile loading interface for CLI commands,
replacing duplicated patterns across apply.py, scan.py, and serve.py.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, NoReturn

import click

from .exit_codes import ExitCode
from .output import error_exit

if TYPE_CHECKING:
    from video_policy_orchestrator.config.models import Profile


def load_profile_or_exit(
    profile_name: str,
    json_output: bool = False,
    verbose: bool = False,
) -> Profile:
    """Load a profile with consistent error handling.

    Loads the named profile and handles errors with appropriate
    output formatting and available profile suggestions.

    Args:
        profile_name: Name of profile to load (without .yaml extension).
        json_output: Whether to format errors as JSON.
        verbose: Whether to print verbose output on success.

    Returns:
        Loaded Profile object.

    Note:
        Exits the process if profile cannot be loaded.
    """
    from video_policy_orchestrator.config.profiles import (
        ProfileError,
        ProfileNotFoundError,
        load_profile,
    )

    try:
        profile = load_profile(profile_name)
        if verbose and not json_output:
            click.echo(f"Using profile: {profile.name}")
        return profile
    except ProfileNotFoundError as e:
        _show_available_profiles_and_exit(str(e), json_output)
    except ProfileError as e:
        error_exit(str(e), ExitCode.CONFIG_ERROR, json_output)


def _show_available_profiles_and_exit(
    error_msg: str,
    json_output: bool,
) -> NoReturn:
    """Show error with available profiles and exit.

    Args:
        error_msg: The error message to display.
        json_output: Whether to format as JSON.

    Note:
        This function never returns; it always calls sys.exit().
    """
    from video_policy_orchestrator.config.profiles import list_profiles

    if json_output:
        error_exit(error_msg, ExitCode.PROFILE_NOT_FOUND, json_output)
    else:
        click.echo(f"Error: {error_msg}", err=True)
        available = list_profiles()
        if available:
            click.echo("\nAvailable profiles:", err=True)
            for name in sorted(available):
                click.echo(f"  - {name}", err=True)
        sys.exit(ExitCode.PROFILE_NOT_FOUND)


def validate_profile_name(profile_name: str) -> bool:
    """Validate that a profile name is well-formed.

    Args:
        profile_name: Profile name to validate.

    Returns:
        True if valid, False otherwise.
    """
    import re

    return bool(re.match(r"^[a-zA-Z0-9_-]+$", profile_name))
