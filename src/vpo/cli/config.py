"""CLI commands for configuration management.

This module provides commands for managing configuration profiles
and validating the base config.toml file.
"""

import json
import logging
from pathlib import Path

import click

from vpo.cli.exit_codes import ExitCode
from vpo.config.profiles import (
    ProfileError,
    ProfileNotFoundError,
    get_profiles_directory,
    list_profiles,
    load_profile,
    validate_profile,
)

logger = logging.getLogger(__name__)


@click.group("config")
def config_group() -> None:
    """Manage configuration profiles.

    Profiles allow different settings for different libraries or use cases.
    Profiles are stored in ~/.vpo/profiles/ as YAML files.

    Examples:

        # List all profiles
        vpo config list

        # Show profile details
        vpo config show movies

        # Validate a profile
        vpo config validate movies
    """
    pass


@config_group.command("list")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output in JSON format.",
)
def list_config_cmd(json_output: bool) -> None:
    """List available configuration profiles.

    Profiles are stored in ~/.vpo/profiles/ as YAML files.

    Examples:

        # List all profiles
        vpo config list

        # Output as JSON
        vpo config list --json
    """
    profile_names = list_profiles()

    if json_output:
        _output_profiles_json(profile_names)
        return

    if not profile_names:
        profiles_dir = get_profiles_directory()
        click.echo(f"No profiles found in {profiles_dir}")
        click.echo("\nTo create a profile, add a YAML file to the profiles directory.")
        click.echo("Example: ~/.vpo/profiles/movies.yaml")
        return

    # Load each profile to get details
    profiles_data = []
    for name in sorted(profile_names):
        try:
            profile = load_profile(name)
            policy_str = str(profile.default_policy) if profile.default_policy else "-"
            profiles_data.append(
                {
                    "name": profile.name,
                    "description": profile.description or "-",
                    "policy": policy_str,
                }
            )
        except ProfileError as e:
            logger.debug("Failed to load profile '%s': %s", name, e)
            profiles_data.append(
                {
                    "name": name,
                    "description": f"(error: {e})",
                    "policy": "-",
                }
            )

    # Print header
    click.echo(f"{'NAME':<15} {'DESCRIPTION':<40} {'POLICY':<30}")
    click.echo("-" * 85)

    # Print profiles
    for p in profiles_data:
        desc = p["description"][:40] if len(p["description"]) > 40 else p["description"]
        policy = p["policy"][:30] if len(p["policy"]) > 30 else p["policy"]
        click.echo(f"{p['name']:<15} {desc:<40} {policy:<30}")


def _output_profiles_json(profile_names: list[str]) -> None:
    """Output profiles list in JSON format."""
    data = []
    for name in sorted(profile_names):
        try:
            profile = load_profile(name)
            profile_data = {
                "name": profile.name,
                "description": profile.description,
                "default_policy": str(profile.default_policy)
                if profile.default_policy
                else None,
            }

            # Include config sections if present
            if profile.behavior:
                behavior = profile.behavior
                profile_data["behavior"] = {
                    "warn_on_missing_features": behavior.warn_on_missing_features,
                    "show_upgrade_suggestions": behavior.show_upgrade_suggestions,
                }
            if profile.logging:
                profile_data["logging"] = {
                    "level": profile.logging.level,
                    "file": str(profile.logging.file) if profile.logging.file else None,
                    "format": profile.logging.format,
                }
            if profile.jobs:
                profile_data["jobs"] = {
                    "retention_days": profile.jobs.retention_days,
                    "auto_purge": profile.jobs.auto_purge,
                }

            data.append(profile_data)
        except ProfileError as e:
            logger.debug("Failed to load profile '%s': %s", name, e)
            data.append(
                {
                    "name": name,
                    "error": str(e),
                }
            )
    click.echo(json.dumps(data, indent=2))


@config_group.command("show")
@click.argument("profile_name")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output in JSON format.",
)
def show_config(profile_name: str, json_output: bool) -> None:
    """Show detailed information about a profile.

    PROFILE_NAME is the name of the profile (without .yaml extension).

    Examples:

        # Show profile details
        vpo config show movies

        # Output as JSON
        vpo config show movies --json
    """
    try:
        profile = load_profile(profile_name)
    except ProfileNotFoundError:
        available = list_profiles()
        click.echo(f"Error: Profile '{profile_name}' not found.", err=True)
        if available:
            click.echo("\nAvailable profiles:", err=True)
            for name in sorted(available):
                click.echo(f"  - {name}", err=True)
        raise click.Abort()
    except ProfileError as e:
        raise click.ClickException(str(e))

    if json_output:
        _output_profile_json(profile)
        return

    _output_profile_human(profile)


def _output_profile_json(profile) -> None:
    """Output profile in JSON format."""
    policy_str = str(profile.default_policy) if profile.default_policy else None
    data = {
        "name": profile.name,
        "description": profile.description,
        "location": str(get_profiles_directory() / f"{profile.name}.yaml"),
        "default_policy": policy_str,
    }

    if profile.tools:
        data["tools"] = {
            "ffmpeg": str(profile.tools.ffmpeg) if profile.tools.ffmpeg else None,
            "ffprobe": str(profile.tools.ffprobe) if profile.tools.ffprobe else None,
            "mkvmerge": str(profile.tools.mkvmerge) if profile.tools.mkvmerge else None,
            "mkvpropedit": str(profile.tools.mkvpropedit)
            if profile.tools.mkvpropedit
            else None,
        }

    if profile.behavior:
        data["behavior"] = {
            "warn_on_missing_features": profile.behavior.warn_on_missing_features,
            "show_upgrade_suggestions": profile.behavior.show_upgrade_suggestions,
        }

    if profile.logging:
        data["logging"] = {
            "level": profile.logging.level,
            "file": str(profile.logging.file) if profile.logging.file else None,
            "format": profile.logging.format,
            "include_stderr": profile.logging.include_stderr,
            "max_bytes": profile.logging.max_bytes,
            "backup_count": profile.logging.backup_count,
        }

    if profile.jobs:
        data["jobs"] = {
            "retention_days": profile.jobs.retention_days,
            "auto_purge": profile.jobs.auto_purge,
            "temp_directory": str(profile.jobs.temp_directory)
            if profile.jobs.temp_directory
            else None,
            "backup_original": profile.jobs.backup_original,
        }

    # Add validation status
    errors = validate_profile(profile)
    data["validation"] = {
        "valid": len(errors) == 0,
        "errors": errors,
    }

    click.echo(json.dumps(data, indent=2))


def _output_profile_human(profile) -> None:
    """Output profile in human-readable format."""
    profiles_dir = get_profiles_directory()

    click.echo(f"\nProfile: {profile.name}")
    click.echo("-" * 50)

    if profile.description:
        click.echo(f"  Description: {profile.description}")
    click.echo(f"  Location:    {profiles_dir / f'{profile.name}.yaml'}")

    if profile.default_policy:
        click.echo(f"\n  Default Policy: {profile.default_policy}")

    if profile.tools:
        click.echo("\n  Tools:")
        if profile.tools.ffmpeg:
            click.echo(f"    ffmpeg:       {profile.tools.ffmpeg}")
        if profile.tools.ffprobe:
            click.echo(f"    ffprobe:      {profile.tools.ffprobe}")
        if profile.tools.mkvmerge:
            click.echo(f"    mkvmerge:     {profile.tools.mkvmerge}")
        if profile.tools.mkvpropedit:
            click.echo(f"    mkvpropedit:  {profile.tools.mkvpropedit}")

    if profile.behavior:
        click.echo("\n  Behavior:")
        click.echo(
            f"    warn_on_missing_features: {profile.behavior.warn_on_missing_features}"
        )
        click.echo(
            f"    show_upgrade_suggestions: {profile.behavior.show_upgrade_suggestions}"
        )

    if profile.logging:
        click.echo("\n  Logging:")
        click.echo(f"    level:         {profile.logging.level}")
        if profile.logging.file:
            click.echo(f"    file:          {profile.logging.file}")
        click.echo(f"    format:        {profile.logging.format}")

    if profile.jobs:
        click.echo("\n  Jobs:")
        click.echo(f"    retention_days: {profile.jobs.retention_days}")
        click.echo(f"    auto_purge:     {profile.jobs.auto_purge}")

    # Validate profile
    errors = validate_profile(profile)
    if errors:
        click.echo("\n  " + click.style("Validation Errors:", fg="yellow"))
        for error in errors:
            click.echo(f"    - {click.style(error, fg='red')}")
    else:
        click.echo("\n  " + click.style("Validation: OK", fg="green"))

    click.echo("")


@config_group.command("validate")
@click.argument("profile_name")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output in JSON format.",
)
def validate_config(profile_name: str, json_output: bool) -> None:
    """Validate a configuration profile.

    PROFILE_NAME is the name of the profile (without .yaml extension).

    Examples:

        # Validate a profile
        vpo config validate movies

        # Output as JSON
        vpo config validate movies --json
    """
    try:
        profile = load_profile(profile_name)
    except ProfileNotFoundError:
        if json_output:
            click.echo(json.dumps({"valid": False, "error": "Profile not found"}))
        else:
            click.echo(f"Error: Profile '{profile_name}' not found.", err=True)
        raise SystemExit(ExitCode.PROFILE_NOT_FOUND)
    except ProfileError as e:
        if json_output:
            click.echo(json.dumps({"valid": False, "error": str(e)}))
        else:
            click.echo(f"Error: {e}", err=True)
        raise SystemExit(ExitCode.CONFIG_ERROR)

    errors = validate_profile(profile)

    if json_output:
        click.echo(
            json.dumps(
                {
                    "name": profile.name,
                    "valid": len(errors) == 0,
                    "errors": errors,
                },
                indent=2,
            )
        )
    else:
        if errors:
            click.echo(f"Profile '{profile_name}' has validation errors:")
            for error in errors:
                click.echo(f"  - {error}")
            raise SystemExit(ExitCode.CONFIG_ERROR)
        else:
            click.echo(f"Profile '{profile_name}' is valid.")


@config_group.command("create")
@click.argument("profile_name")
@click.option(
    "--policy",
    "-p",
    type=click.Path(exists=True),
    help="Default policy file for this profile.",
)
@click.option(
    "--description",
    "-d",
    help="Description of this profile.",
)
def create_config(
    profile_name: str, policy: str | None, description: str | None
) -> None:
    """Create a new configuration profile.

    PROFILE_NAME is the name for the new profile (without .yaml extension).

    Examples:

        # Create a basic profile
        vpo config create movies

        # Create with default policy
        vpo config create movies --policy ~/.vpo/policies/normalize.yaml

        # Create with description
        vpo config create movies -d "Profile for movie library"
    """
    from pathlib import Path

    profiles_dir = get_profiles_directory()
    profile_path = profiles_dir / f"{profile_name}.yaml"

    if profile_path.exists():
        raise click.ClickException(f"Profile '{profile_name}' already exists.")

    # Build profile content
    content_lines = [
        f"name: {profile_name}",
    ]

    if description:
        content_lines.append(f"description: {description}")

    if policy:
        policy_path = Path(policy).resolve()
        content_lines.append(f"default_policy: {policy_path}")

    content = "\n".join(content_lines) + "\n"

    # Ensure profiles directory exists
    profiles_dir.mkdir(parents=True, exist_ok=True)

    # Write profile
    profile_path.write_text(content)
    click.echo(f"Created profile: {profile_path}")


@config_group.command("check")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to config.toml (default: ~/.vpo/config.toml).",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output in JSON format.",
)
def check_config(config_path: Path | None, json_output: bool) -> None:
    """Validate the base config.toml file.

    Loads the config file with strict parsing, constructs the full
    VPOConfig, and runs cross-field validation checks.

    Examples:

        # Check default config
        vpo config check

        # Check specific config file
        vpo config check --config /path/to/config.toml

        # Output as JSON
        vpo config check --json
    """
    from vpo.config.loader import get_config, validate_config
    from vpo.config.toml_parser import TomlParseError

    errors: list[str] = []

    # Load with strict=True to catch parse errors
    try:
        config = get_config(config_path=config_path, strict=True)
    except TomlParseError as e:
        errors.append(f"TOML parse error: {e}")
        if json_output:
            click.echo(json.dumps({"valid": False, "errors": errors}, indent=2))
        else:
            click.echo(click.style("Config file has errors:", fg="red"), err=True)
            for error in errors:
                click.echo(f"  - {error}", err=True)
        raise SystemExit(ExitCode.CONFIG_ERROR)
    except ValueError as e:
        errors.append(f"Validation error: {e}")
        if json_output:
            click.echo(json.dumps({"valid": False, "errors": errors}, indent=2))
        else:
            click.echo(click.style("Config file has errors:", fg="red"), err=True)
            for error in errors:
                click.echo(f"  - {error}", err=True)
        raise SystemExit(ExitCode.CONFIG_ERROR)

    # Run cross-field validation
    errors = validate_config(config)

    if json_output:
        click.echo(json.dumps({"valid": len(errors) == 0, "errors": errors}, indent=2))
        if errors:
            raise SystemExit(ExitCode.CONFIG_ERROR)
    else:
        if errors:
            click.echo(click.style("Config file has errors:", fg="red"), err=True)
            for error in errors:
                click.echo(f"  - {error}", err=True)
            raise SystemExit(ExitCode.CONFIG_ERROR)
        else:
            click.echo(click.style("Configuration is valid.", fg="green"))
