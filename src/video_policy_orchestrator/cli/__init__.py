"""CLI module for Video Policy Orchestrator."""

import click


@click.group()
@click.version_option(package_name="video-policy-orchestrator")
def main() -> None:
    """Video Policy Orchestrator - Scan, organize, and transform video libraries."""
    pass


# Import subcommands to register them
from video_policy_orchestrator.cli import scan as _scan  # noqa: E402, F401
