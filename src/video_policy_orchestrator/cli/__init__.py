"""CLI module for Video Policy Orchestrator."""

import click


@click.group()
@click.version_option(package_name="video-policy-orchestrator")
def main() -> None:
    """Video Policy Orchestrator - Scan, organize, and transform video libraries."""
    pass


# Defer import to avoid circular dependency
def _register_commands():
    from video_policy_orchestrator.cli import scan  # noqa: F401
    from video_policy_orchestrator.cli.apply import apply_command
    from video_policy_orchestrator.cli.inspect import inspect_command

    main.add_command(inspect_command)
    main.add_command(apply_command)


_register_commands()
