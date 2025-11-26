"""CLI command for VPO initialization.

Provides the `vpo init` command to set up VPO's data directory
with configuration files and default policies.
"""

import logging
from pathlib import Path

import click

from video_policy_orchestrator.config.loader import get_data_dir
from video_policy_orchestrator.config.templates import (
    InitResult,
    check_initialization_state,
    run_init,
)

logger = logging.getLogger(__name__)


def _get_data_dir(data_dir_option: Path | None) -> Path:
    """Get the data directory to use for initialization.

    Priority:
    1. --data-dir CLI option
    2. VPO_DATA_DIR environment variable (via get_data_dir())
    3. Default (~/.vpo)

    Args:
        data_dir_option: Value from --data-dir option, or None.

    Returns:
        Path to use for initialization.
    """
    if data_dir_option is not None:
        return data_dir_option

    return get_data_dir()


def _display_result(result: InitResult, force: bool) -> None:
    """Display the result of initialization to the user.

    Args:
        result: The initialization result.
        force: Whether --force was used.
    """
    if result.dry_run:
        # Dry-run output
        if result.success:
            click.echo("")
            for directory in result.created_directories:
                click.echo(f"Would create {directory}/")
            for file in result.created_files:
                click.echo(f"Would create {file}")
            click.echo("")
            click.echo("No changes made (dry run).")
        else:
            click.echo(f"Error: {result.error}", err=True)
    elif result.success:
        # Successful initialization
        if force and result.skipped_files:
            click.echo(
                f"Warning: Overwriting existing configuration at {result.data_dir}/",
                err=True,
            )
            click.echo("")

        # Directories are never "replaced" - they're reused
        for directory in result.created_directories:
            click.echo(f"Created {directory}/")

        for file in result.created_files:
            if force and file in result.skipped_files:
                click.echo(f"Replaced {file}")
            else:
                click.echo(f"Created {file}")

        click.echo("")
        if force:
            click.echo("VPO re-initialized with defaults.")
        else:
            click.echo("VPO initialized successfully!")

        click.echo("")
        click.echo("Next steps:")
        click.echo(f"  1. Review configuration: {result.data_dir}/config.toml")
        click.echo("  2. Verify setup: vpo doctor")
        click.echo("  3. Scan your library: vpo scan /path/to/videos")
    else:
        # Failed initialization
        _display_error(result)


def _display_error(result: InitResult) -> None:
    """Display an initialization error to the user.

    Args:
        result: The failed initialization result.
    """
    click.echo(f"Error: {result.error}", err=True)

    # Show existing files if this is an already-initialized error
    if result.skipped_files and "already initialized" in (result.error or "").lower():
        click.echo("")
        click.echo("Existing files:")
        for path in result.skipped_files:
            # Show relative name for cleaner output
            click.echo(f"  - {path.name}")
        click.echo("")
        click.echo("Use --force to overwrite existing configuration.")


def _display_existing_state(data_dir: Path) -> None:
    """Display the current state when already initialized.

    Args:
        data_dir: The data directory path.
    """
    state = check_initialization_state(data_dir)

    click.echo(f"Error: VPO is already initialized at {data_dir}", err=True)
    click.echo("")
    click.echo("Existing files:")
    for path in state.existing_files:
        click.echo(f"  - {path.name}")
    click.echo("")
    click.echo("Use --force to overwrite existing configuration.")


@click.command("init")
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Use custom data directory instead of ~/.vpo/",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing configuration files.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be created without making changes.",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Suppress output except for errors.",
)
def init_command(
    data_dir: Path | None,
    force: bool,
    dry_run: bool,
    quiet: bool,
) -> None:
    """Initialize VPO configuration directory.

    Creates the VPO data directory (~/.vpo by default) with:

    \b
    - config.toml: Configuration file with documented settings
    - policies/: Directory for policy files
    - policies/default.yaml: Starter policy demonstrating common patterns
    - plugins/: Directory for user plugins

    \b
    Examples:
        # Initialize with default location
        vpo init

    \b
        # Preview what would be created
        vpo init --dry-run

    \b
        # Use custom data directory
        vpo init --data-dir /mnt/nas/vpo

    \b
        # Re-initialize (overwrites existing config)
        vpo init --force
    """
    # Resolve the data directory
    target_dir = _get_data_dir(data_dir)

    logger.info(
        "Init command: data_dir=%s, force=%s, dry_run=%s",
        target_dir,
        force,
        dry_run,
    )

    # Run initialization
    result = run_init(target_dir, force=force, dry_run=dry_run)

    # Display results (unless quiet mode, but always show errors)
    if not quiet or not result.success:
        _display_result(result, force)

    # Exit with appropriate code
    if not result.success:
        raise SystemExit(1)
