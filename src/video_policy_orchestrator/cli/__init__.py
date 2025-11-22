"""CLI module for Video Policy Orchestrator."""

import click


@click.group()
@click.version_option(package_name="video-policy-orchestrator")
@click.option(
    "--force-load-plugins",
    is_flag=True,
    help="Force load plugins even if version incompatible or unacknowledged",
)
@click.pass_context
def main(ctx: click.Context, force_load_plugins: bool) -> None:
    """Video Policy Orchestrator - Scan, organize, and transform video libraries."""
    ctx.ensure_object(dict)
    ctx.obj["force_load_plugins"] = force_load_plugins


# Defer import to avoid circular dependency
def _register_commands():
    from video_policy_orchestrator.cli import scan  # noqa: F401
    from video_policy_orchestrator.cli.apply import apply_command
    from video_policy_orchestrator.cli.doctor import doctor_command
    from video_policy_orchestrator.cli.inspect import inspect_command
    from video_policy_orchestrator.cli.plugins import plugins

    main.add_command(inspect_command)
    main.add_command(apply_command)
    main.add_command(doctor_command)
    main.add_command(plugins)


_register_commands()
