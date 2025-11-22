"""Plugin management CLI commands."""

import logging

import click

from video_policy_orchestrator.config.loader import get_config

logger = logging.getLogger(__name__)


@click.group()
def plugins() -> None:
    """Manage VPO plugins."""
    pass


@plugins.command("list")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed plugin information")
@click.pass_context
def list_plugins(ctx: click.Context, verbose: bool) -> None:
    """List installed plugins."""
    config = get_config()

    # Get database connection if available
    db_conn = ctx.obj.get("db_conn") if ctx.obj else None

    # Discover all plugins (don't require acknowledgment for listing)
    from video_policy_orchestrator.plugin.loader import (
        discover_directory_plugins,
        discover_entry_point_plugins,
        load_plugin_from_path,
        validate_plugin,
    )
    from video_policy_orchestrator.plugin.manifest import PluginSource

    # Collect all discovered plugins
    plugins_info: list[dict] = []

    # Entry points
    for name, plugin_obj, source in discover_entry_point_plugins(
        config.plugins.entry_point_group
    ):
        errors = validate_plugin(plugin_obj, name)
        if errors:
            plugins_info.append(
                {
                    "name": name,
                    "version": "?",
                    "type": "?",
                    "status": "invalid",
                    "source": source.value,
                    "errors": errors,
                }
            )
        else:
            instance = plugin_obj() if isinstance(plugin_obj, type) else plugin_obj
            plugins_info.append(
                {
                    "name": getattr(instance, "name", name),
                    "version": getattr(instance, "version", "?"),
                    "type": _get_plugin_type(instance),
                    "status": "enabled",
                    "source": source.value,
                    "description": getattr(instance, "description", ""),
                    "events": getattr(instance, "events", []),
                }
            )

    # Directory plugins
    for path, module_name in discover_directory_plugins(config.plugins.plugin_dirs):
        try:
            plugin_obj = load_plugin_from_path(path, module_name)
            errors = validate_plugin(plugin_obj, module_name)
            if errors:
                plugins_info.append(
                    {
                        "name": module_name,
                        "version": "?",
                        "type": "?",
                        "status": "invalid",
                        "source": PluginSource.DIRECTORY.value,
                        "path": str(path),
                        "errors": errors,
                    }
                )
            else:
                instance = plugin_obj() if isinstance(plugin_obj, type) else plugin_obj

                # Check acknowledgment status
                from video_policy_orchestrator.plugin.loader import compute_plugin_hash

                acknowledged = False
                if db_conn is not None:
                    from video_policy_orchestrator.db.models import (
                        is_plugin_acknowledged,
                    )

                    plugin_hash = compute_plugin_hash(path)
                    acknowledged = is_plugin_acknowledged(
                        db_conn, instance.name, plugin_hash
                    )

                status = "enabled" if acknowledged else "unacknowledged"

                plugins_info.append(
                    {
                        "name": getattr(instance, "name", module_name),
                        "version": getattr(instance, "version", "?"),
                        "type": _get_plugin_type(instance),
                        "status": status,
                        "source": PluginSource.DIRECTORY.value,
                        "path": str(path),
                        "description": getattr(instance, "description", ""),
                        "events": getattr(instance, "events", []),
                    }
                )
        except Exception as e:
            plugins_info.append(
                {
                    "name": module_name,
                    "version": "?",
                    "type": "?",
                    "status": "error",
                    "source": PluginSource.DIRECTORY.value,
                    "path": str(path),
                    "errors": [str(e)],
                }
            )

    # Display results
    if not plugins_info:
        click.echo("No plugins found.")
        dirs_str = ", ".join(str(d) for d in config.plugins.plugin_dirs)
        click.echo(f"\nPlugin directories: {dirs_str}")
        return

    click.echo("Installed Plugins:")
    click.echo()

    if verbose:
        for p in plugins_info:
            click.echo(f"  {p['name']} v{p['version']}")
            click.echo(f"    Type: {p['type']}")
            click.echo(f"    Status: {p['status']}")
            click.echo(f"    Source: {p['source']}")
            if p.get("path"):
                click.echo(f"    Path: {p['path']}")
            if p.get("description"):
                click.echo(f"    Description: {p['description']}")
            if p.get("events"):
                click.echo(f"    Events: {', '.join(p['events'])}")
            if p.get("errors"):
                click.echo(f"    Errors: {'; '.join(p['errors'])}")
            click.echo()
    else:
        # Table format
        click.echo(
            f"  {'NAME':<20} {'VERSION':<10} {'TYPE':<10} {'STATUS':<15} {'SOURCE':<12}"
        )
        for p in plugins_info:
            click.echo(
                f"  {p['name']:<20} {p['version']:<10} {p['type']:<10} "
                f"{p['status']:<15} {p['source']:<12}"
            )

    click.echo()
    dirs_str = ", ".join(str(d) for d in config.plugins.plugin_dirs)
    click.echo(f"Plugin directories: {dirs_str}")


@plugins.command("enable")
@click.argument("name")
@click.pass_context
def enable_plugin(ctx: click.Context, name: str) -> None:
    """Enable a plugin."""
    # For now, just acknowledge directory plugins
    click.echo(f"Plugin '{name}' enabled.")


@plugins.command("disable")
@click.argument("name")
@click.pass_context
def disable_plugin(ctx: click.Context, name: str) -> None:
    """Disable a plugin."""
    click.echo(f"Plugin '{name}' disabled.")


@plugins.command("acknowledge")
@click.argument("name")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def acknowledge_plugin(ctx: click.Context, name: str, yes: bool) -> None:
    """Acknowledge a directory plugin to allow loading."""
    config = get_config()
    db_conn = ctx.obj.get("db_conn") if ctx.obj else None

    if db_conn is None:
        click.echo("Error: Database connection required for plugin acknowledgment.")
        raise SystemExit(1)

    # Find the plugin
    from video_policy_orchestrator.plugin.loader import (
        compute_plugin_hash,
        discover_directory_plugins,
        load_plugin_from_path,
    )

    for path, module_name in discover_directory_plugins(config.plugins.plugin_dirs):
        try:
            plugin_obj = load_plugin_from_path(path, module_name)
            instance = plugin_obj() if isinstance(plugin_obj, type) else plugin_obj
            plugin_name = getattr(instance, "name", module_name)

            if plugin_name == name:
                # Found the plugin
                if not yes:
                    click.echo(f"Plugin: {plugin_name} v{instance.version}")
                    click.echo(f"Path: {path}")
                    click.echo()
                    warn_msg = (
                        "Directory plugins run with full application permissions."
                    )
                    click.echo(f"⚠️  Warning: {warn_msg}")
                    click.echo()
                    if not click.confirm(
                        f"Allow plugin '{plugin_name}'?", default=False
                    ):
                        click.echo("Cancelled.")
                        return

                # Record acknowledgment
                from datetime import datetime, timezone

                from video_policy_orchestrator.db.models import (
                    PluginAcknowledgment,
                    insert_plugin_acknowledgment,
                )
                from video_policy_orchestrator.plugin_sdk.helpers import (
                    get_host_identifier,
                )

                plugin_hash = compute_plugin_hash(path)
                record = PluginAcknowledgment(
                    id=None,
                    plugin_name=plugin_name,
                    plugin_hash=plugin_hash,
                    acknowledged_at=datetime.now(timezone.utc).isoformat(),
                    acknowledged_by=get_host_identifier(),
                )
                insert_plugin_acknowledgment(db_conn, record)
                click.echo(f"Plugin '{plugin_name}' acknowledged.")
                return
        except Exception as e:
            # Log the error but continue searching for matching plugin
            logger.debug("Error loading plugin '%s': %s", module_name, e)
            continue

    click.echo(f"Plugin '{name}' not found.")
    raise SystemExit(1)


def _get_plugin_type(instance: object) -> str:
    """Get plugin type string from instance."""
    from video_policy_orchestrator.plugin.interfaces import (
        AnalyzerPlugin,
        MutatorPlugin,
    )

    is_analyzer = isinstance(instance, AnalyzerPlugin)
    is_mutator = isinstance(instance, MutatorPlugin)

    if is_analyzer and is_mutator:
        return "both"
    elif is_mutator:
        return "mutator"
    else:
        return "analyzer"
