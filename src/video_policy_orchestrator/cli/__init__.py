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


_register_commands()
