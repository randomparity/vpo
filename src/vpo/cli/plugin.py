"""Plugin management CLI commands.

Renamed from plugins.py for consistency with other singular group names.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import click

from vpo.cli.exit_codes import ExitCode
from vpo.config.loader import get_config

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredPlugin:
    """Information about a discovered plugin."""

    name: str
    instance: object
    source: str
    path: Path | None = None


def _find_plugin_by_name(
    name: str,
    entry_point_group: str,
    plugin_dirs: list[Path],
) -> DiscoveredPlugin | None:
    """Find a plugin by name across all sources.

    Args:
        name: Plugin name to find.
        entry_point_group: Entry point group to search.
        plugin_dirs: Directories to search for directory plugins.

    Returns:
        DiscoveredPlugin if found, None otherwise.
    """
    from vpo.plugin.loader import (
        discover_directory_plugins,
        discover_entry_point_plugins,
        load_plugin_from_path,
    )

    # Search entry points
    for ep_name, plugin_obj, source in discover_entry_point_plugins(entry_point_group):
        instance = plugin_obj() if isinstance(plugin_obj, type) else plugin_obj
        plugin_name = getattr(instance, "name", ep_name)
        if plugin_name == name:
            return DiscoveredPlugin(
                name=plugin_name,
                instance=instance,
                source=source.value,
                path=None,
            )

    # Search directory plugins
    for path, module_name in discover_directory_plugins(plugin_dirs):
        try:
            plugin_obj = load_plugin_from_path(path, module_name)
            instance = plugin_obj() if isinstance(plugin_obj, type) else plugin_obj
            plugin_name = getattr(instance, "name", module_name)
            if plugin_name == name:
                return DiscoveredPlugin(
                    name=plugin_name,
                    instance=instance,
                    source="directory",
                    path=path,
                )
        except Exception:  # nosec B112 - skip failed plugin loads during search
            continue

    return None


@click.group("plugin")
def plugin_group() -> None:
    """Manage VPO plugins.

    Commands for listing, enabling, and managing plugins.

    Examples:

        # List installed plugins
        vpo plugin list

        # Show plugin details
        vpo plugin info my-plugin

        # Enable a plugin
        vpo plugin enable my-plugin

        # Disable a plugin
        vpo plugin disable my-plugin
    """
    pass


@plugin_group.command("list")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed plugin information")
@click.pass_context
def list_plugins(ctx: click.Context, verbose: bool) -> None:
    """List installed plugins."""
    config = get_config()

    # Get database connection if available
    db_conn = ctx.obj.get("db_conn") if ctx.obj else None

    # Discover all plugins (don't require acknowledgment for listing)
    from vpo.plugin.loader import (
        discover_directory_plugins,
        discover_entry_point_plugins,
        load_plugin_from_path,
        validate_plugin,
    )
    from vpo.plugin.manifest import PluginSource

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
                from vpo.plugin.loader import compute_plugin_hash

                acknowledged = False
                if db_conn is not None:
                    from vpo.db import (
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


@plugin_group.command("info")
@click.argument("name")
@click.pass_context
def info_plugin(ctx: click.Context, name: str) -> None:
    """Show detailed information about a plugin.

    NAME is the plugin name to show information for.

    Examples:

        vpo plugin info my-plugin
    """
    config = get_config()
    db_conn = ctx.obj.get("db_conn") if ctx.obj else None

    plugin = _find_plugin_by_name(
        name,
        config.plugins.entry_point_group,
        config.plugins.plugin_dirs,
    )

    if plugin is None:
        click.echo(f"Plugin '{name}' not found.")
        raise SystemExit(ExitCode.TARGET_NOT_FOUND)

    instance = plugin.instance
    click.echo(f"\nPlugin: {plugin.name}")
    click.echo("-" * 50)
    click.echo(f"  Version:     {getattr(instance, 'version', '?')}")
    click.echo(f"  Type:        {_get_plugin_type(instance)}")
    click.echo(f"  Source:      {plugin.source}")

    if plugin.path:
        click.echo(f"  Path:        {plugin.path}")

    if hasattr(instance, "description") and instance.description:
        click.echo(f"  Description: {instance.description}")
    if hasattr(instance, "events") and instance.events:
        click.echo(f"  Events:      {', '.join(instance.events)}")

    # Check acknowledgment for directory plugins
    if plugin.path and db_conn is not None:
        from vpo.db import is_plugin_acknowledged
        from vpo.plugin.loader import compute_plugin_hash

        plugin_hash = compute_plugin_hash(plugin.path)
        acknowledged = is_plugin_acknowledged(db_conn, name, plugin_hash)
        status = "enabled" if acknowledged else "unacknowledged"
        click.echo(f"  Status:      {status}")

    click.echo()


@plugin_group.command("enable")
@click.argument("name")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def enable_plugin(ctx: click.Context, name: str, yes: bool) -> None:
    """Enable a plugin by acknowledging it.

    For directory plugins, this records your acknowledgment that the
    plugin should be loaded. Entry point plugins are always enabled.

    NAME is the plugin name to enable.

    Examples:

        vpo plugin enable my-plugin
        vpo plugin enable --yes my-plugin
    """
    config = get_config()
    db_conn = ctx.obj.get("db_conn") if ctx.obj else None

    if db_conn is None:
        click.echo("Error: Database connection required for plugin acknowledgment.")
        raise SystemExit(ExitCode.DATABASE_ERROR)

    plugin = _find_plugin_by_name(
        name,
        config.plugins.entry_point_group,
        config.plugins.plugin_dirs,
    )

    if plugin is None:
        click.echo(f"Plugin '{name}' not found.")
        raise SystemExit(ExitCode.TARGET_NOT_FOUND)

    # Entry point plugins are always enabled
    if plugin.path is None:
        click.echo(f"Plugin '{name}' is an entry point plugin and is always enabled.")
        return

    instance = plugin.instance

    # Confirm enablement
    if not yes:
        click.echo(f"Plugin: {plugin.name} v{getattr(instance, 'version', '?')}")
        click.echo(f"Path: {plugin.path}")
        click.echo()
        click.echo("Warning: Directory plugins run with full application permissions.")
        click.echo()
        if not click.confirm(f"Allow plugin '{plugin.name}'?", default=False):
            click.echo("Cancelled.")
            return

    # Record acknowledgment
    from datetime import datetime, timezone

    from vpo.db import PluginAcknowledgment, insert_plugin_acknowledgment
    from vpo.plugin.loader import compute_plugin_hash
    from vpo.plugin_sdk.helpers import get_host_identifier

    plugin_hash = compute_plugin_hash(plugin.path)
    record = PluginAcknowledgment(
        id=None,
        plugin_name=plugin.name,
        plugin_hash=plugin_hash,
        acknowledged_at=datetime.now(timezone.utc).isoformat(),
        acknowledged_by=get_host_identifier(),
    )
    insert_plugin_acknowledgment(db_conn, record)
    click.echo(f"Plugin '{plugin.name}' enabled.")


@plugin_group.command("disable")
@click.argument("name")
@click.pass_context
def disable_plugin(ctx: click.Context, name: str) -> None:
    """Disable a plugin.

    For directory plugins, this removes the acknowledgment record.

    NAME is the plugin name to disable.

    Examples:

        vpo plugin disable my-plugin
    """
    db_conn = ctx.obj.get("db_conn") if ctx.obj else None

    if db_conn is None:
        click.echo("Error: Database connection required for plugin management.")
        raise SystemExit(ExitCode.DATABASE_ERROR)

    # Remove acknowledgment if it exists
    from vpo.db import delete_plugin_acknowledgment

    deleted = delete_plugin_acknowledgment(db_conn, name)

    if deleted:
        click.echo(f"Plugin '{name}' disabled.")
    else:
        click.echo(f"Plugin '{name}' was not enabled or does not exist.")


def _get_plugin_type(instance: object) -> str:
    """Get plugin type string from instance."""
    from vpo.plugin.interfaces import (
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
