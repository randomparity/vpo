"""VPO doctor command for checking external tool health.

This module provides the 'vpo doctor' command to check external tool
availability, versions, and capabilities.
"""

import shutil
import sys
from pathlib import Path

import click

from vpo.cli.exit_codes import DOCTOR_EXIT_CODES
from vpo.config import VPOConfig, get_config
from vpo.core.formatting import format_file_size
from vpo.tools import (
    RequirementLevel,
    check_requirements,
    get_tool_registry,
    get_upgrade_suggestions,
)
from vpo.tools.cache import DEFAULT_CACHE_FILE

# Backward compatibility aliases - prefer using DOCTOR_EXIT_CODES
EXIT_OK = DOCTOR_EXIT_CODES["EXIT_OK"]
EXIT_WARNINGS = DOCTOR_EXIT_CODES["EXIT_WARNINGS"]
EXIT_CRITICAL = DOCTOR_EXIT_CODES["EXIT_CRITICAL"]


def _format_status(available: bool) -> str:
    """Format status for display."""
    return "✓" if available else "✗"


def _format_version(version: str | None) -> str:
    """Format version for display."""
    return version if version else "not found"


@click.command("doctor")
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed capability information",
)
@click.option(
    "--refresh",
    is_flag=True,
    help="Force refresh of tool detection (ignore cache)",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output results as JSON",
)
def doctor_command(verbose: bool, refresh: bool, json_output: bool) -> None:
    """Check external tool availability and capabilities.

    Verifies that all required external tools (ffmpeg, ffprobe, mkvmerge,
    mkvpropedit) are installed and reports their versions and capabilities.

    Exit codes:
      0 - All tools available and requirements met
      1 - Some warnings (outdated versions, missing optional features)
      2 - Critical issues (required tools missing)
    """
    config = get_config()

    # Get tool registry (with optional refresh)
    registry = get_tool_registry(
        force_refresh=refresh,
        ffmpeg_path=config.tools.ffmpeg,
        ffprobe_path=config.tools.ffprobe,
        mkvmerge_path=config.tools.mkvmerge,
        mkvpropedit_path=config.tools.mkvpropedit,
        ttl_hours=config.detection.cache_ttl_hours,
    )

    if json_output:
        _output_json(registry)
        return

    # Display header
    click.echo("VPO External Tool Health Check")
    click.echo("=" * 40)
    click.echo()

    # Check each tool
    has_critical = False
    has_warnings = False

    # FFmpeg family
    click.echo("FFmpeg Tools:")
    click.echo("-" * 20)

    # ffprobe
    ffprobe = registry.ffprobe
    status = _format_status(ffprobe.is_available())
    version = _format_version(ffprobe.version)
    path_info = f" ({ffprobe.path})" if ffprobe.path and verbose else ""
    click.echo(f"  {status} ffprobe: {version}{path_info}")
    if not ffprobe.is_available():
        has_critical = True
        click.echo("    └─ Install ffmpeg: https://ffmpeg.org/download.html")

    # ffmpeg
    ffmpeg = registry.ffmpeg
    status = _format_status(ffmpeg.is_available())
    version = _format_version(ffmpeg.version)
    path_info = f" ({ffmpeg.path})" if ffmpeg.path and verbose else ""
    click.echo(f"  {status} ffmpeg:  {version}{path_info}")
    if not ffmpeg.is_available():
        has_warnings = True  # Not critical if only doing MKV operations
        click.echo("    └─ Install ffmpeg: https://ffmpeg.org/download.html")

    # FFmpeg capabilities (verbose mode)
    if verbose and ffmpeg.is_available():
        caps = ffmpeg.capabilities
        click.echo(f"    ├─ GPL build: {'yes' if caps.is_gpl else 'no'}")
        click.echo(f"    ├─ Encoders: {len(caps.encoders)}")
        click.echo(f"    ├─ Decoders: {len(caps.decoders)}")
        click.echo(f"    ├─ Muxers: {len(caps.muxers)}")
        click.echo(f"    └─ Filters: {len(caps.filters)}")

        # Check for common useful codecs
        common_encoders = ["libx264", "libx265", "aac", "libopus"]
        missing_encoders = [e for e in common_encoders if not caps.has_encoder(e)]
        if missing_encoders:
            click.echo(f"    ⚠ Missing encoders: {', '.join(missing_encoders)}")

    click.echo()

    # MKVToolNix
    click.echo("MKVToolNix:")
    click.echo("-" * 20)

    # mkvmerge
    mkvmerge = registry.mkvmerge
    status = _format_status(mkvmerge.is_available())
    version = _format_version(mkvmerge.version)
    path_info = f" ({mkvmerge.path})" if mkvmerge.path and verbose else ""
    click.echo(f"  {status} mkvmerge:    {version}{path_info}")
    if not mkvmerge.is_available():
        has_warnings = True
        click.echo("    └─ Install mkvtoolnix: https://mkvtoolnix.download/")

    # mkvpropedit
    mkvpropedit = registry.mkvpropedit
    status = _format_status(mkvpropedit.is_available())
    version = _format_version(mkvpropedit.version)
    path_info = f" ({mkvpropedit.path})" if mkvpropedit.path and verbose else ""
    click.echo(f"  {status} mkvpropedit: {version}{path_info}")
    if not mkvpropedit.is_available():
        has_warnings = True
        click.echo("    └─ Install mkvtoolnix: https://mkvtoolnix.download/")

    click.echo()

    # Check requirements
    report = check_requirements(registry)

    # Show requirement issues
    critical_issues = report.get_unsatisfied(RequirementLevel.REQUIRED)
    if critical_issues:
        has_critical = True
        click.echo("Critical Issues:")
        click.echo("-" * 20)
        for result in critical_issues:
            click.echo(f"  ✗ {result.message}")
        click.echo()

    # Show upgrade suggestions (verbose or if there are issues)
    suggestions = get_upgrade_suggestions(registry)
    if suggestions and (verbose or has_warnings):
        click.echo("Upgrade Suggestions:")
        click.echo("-" * 20)
        for suggestion in suggestions:
            click.echo(f"  → {suggestion}")
        click.echo()

    # Cache info (verbose)
    if verbose:
        click.echo("Cache Information:")
        click.echo("-" * 20)
        click.echo(f"  Cache file: {DEFAULT_CACHE_FILE}")
        if registry.cache_valid_until:
            click.echo(f"  Valid until: {registry.cache_valid_until.isoformat()}")
        click.echo()

    # Configuration info (verbose)
    if verbose:
        click.echo("Configuration:")
        click.echo("-" * 20)
        if config.tools.ffmpeg:
            click.echo(f"  ffmpeg path: {config.tools.ffmpeg}")
        if config.tools.ffprobe:
            click.echo(f"  ffprobe path: {config.tools.ffprobe}")
        if config.tools.mkvmerge:
            click.echo(f"  mkvmerge path: {config.tools.mkvmerge}")
        if config.tools.mkvpropedit:
            click.echo(f"  mkvpropedit path: {config.tools.mkvpropedit}")
        if not any(
            [
                config.tools.ffmpeg,
                config.tools.ffprobe,
                config.tools.mkvmerge,
                config.tools.mkvpropedit,
            ]
        ):
            click.echo("  (using system PATH)")
        click.echo()

    # Transcription Plugins
    click.echo("Transcription Plugins:")
    click.echo("-" * 20)
    _show_transcription_plugins(verbose)
    click.echo()

    # Disk Space Status (always show when verbose)
    if verbose:
        click.echo("Disk Space Status:")
        click.echo("-" * 20)
        disk_warning = _show_disk_status(config)
        if disk_warning:
            has_warnings = True
        click.echo()

    # Summary
    click.echo("Summary:")
    click.echo("-" * 20)
    available = registry.get_available_tools()
    missing = registry.get_missing_tools()
    click.echo(f"  Available: {len(available)}/4 ({', '.join(available) or 'none'})")
    if missing:
        click.echo(f"  Missing: {', '.join(missing)}")

    # Exit code
    if has_critical:
        click.echo()
        click.echo("⚠ Critical tools are missing. Some VPO features will not work.")
        sys.exit(EXIT_CRITICAL)
    elif has_warnings:
        click.echo()
        click.echo("Note: Some optional tools are missing or outdated.")
        sys.exit(EXIT_WARNINGS)
    else:
        click.echo()
        click.echo("✓ All tools available and ready.")
        sys.exit(EXIT_OK)


def _output_json(registry) -> None:
    """Output tool registry as JSON."""
    import json

    from vpo.tools.cache import serialize_registry

    data = serialize_registry(registry)
    click.echo(json.dumps(data, indent=2))


def _show_transcription_plugins(verbose: bool) -> None:
    """Show available transcription plugins."""
    from vpo.plugin import get_default_registry
    from vpo.plugin.events import TRANSCRIPTION_REQUESTED

    try:
        # Load plugin registry
        registry = get_default_registry()

        # Get plugins that handle transcription.requested events
        plugins = registry.get_by_event(TRANSCRIPTION_REQUESTED)

        if not plugins:
            click.echo("  ✗ No transcription plugins available")
            click.echo("    └─ Install a transcription plugin (e.g., whisper-local).")
            return

        for loaded_plugin in plugins:
            version = getattr(loaded_plugin.instance, "version", "unknown")
            click.echo(f"  ✓ {loaded_plugin.name} (v{version})")

            if verbose:
                features = []
                supports_fn = getattr(loaded_plugin.instance, "supports_feature", None)
                if supports_fn:
                    if supports_fn("language_detection"):
                        features.append("language detection")
                    if supports_fn("transcription"):
                        features.append("transcription")
                    if supports_fn("gpu"):
                        features.append("GPU")
                if features:
                    click.echo(f"    └─ Features: {', '.join(features)}")

    except Exception as e:
        click.echo(f"  ✗ Error loading transcription plugins: {e}")
        if verbose:
            import traceback

            click.echo(traceback.format_exc(), err=True)


def _show_disk_status(config: VPOConfig) -> bool:
    """Show disk space status and configured threshold.

    Args:
        config: VPOConfig instance.

    Returns:
        True if there's a warning (disk below threshold), False otherwise.
    """
    min_free_percent = config.jobs.min_free_disk_percent

    # Get home directory for VPO data
    vpo_data_dir = Path.home() / ".vpo"

    # Check disk space on VPO data directory (or home if not exists)
    check_path = vpo_data_dir if vpo_data_dir.exists() else Path.home()

    try:
        stat = shutil.disk_usage(check_path)
        total = stat.total
        free = stat.free
        free_percent = (free / total) * 100

        click.echo(f"  VPO data directory: {vpo_data_dir}")
        click.echo(f"  Total disk space: {format_file_size(total)}")
        click.echo(f"  Free disk space: {format_file_size(free)} ({free_percent:.1f}%)")

        if min_free_percent > 0:
            click.echo(f"  Configured threshold: {min_free_percent:.1f}%")
            if free_percent < min_free_percent:
                click.echo(
                    f"  ⚠ Warning: Free space ({free_percent:.1f}%) is below "
                    f"threshold ({min_free_percent:.1f}%)"
                )
                return True
            else:
                click.echo("  ✓ Disk space is above threshold")
        else:
            click.echo("  Threshold check: disabled (min_free_disk_percent = 0)")

        click.echo("  Note: Processing checks the target file's filesystem")

        return False

    except OSError as e:
        click.echo(f"  ✗ Cannot check disk space: {e}")
        return False
