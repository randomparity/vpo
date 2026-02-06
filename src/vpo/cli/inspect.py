"""CLI inspect command for Video Policy Orchestrator."""

import json
import logging
import sys
from pathlib import Path
from typing import Any

import click

from vpo.cli.exit_codes import ExitCode
from vpo.introspector import (
    FFprobeIntrospector,
    MediaIntrospectionError,
    format_human,
    format_json,
)
from vpo.language_analysis import (
    LanguageAnalysisError,
    LanguageAnalysisResult,
    analyze_track_languages,
)
from vpo.language_analysis import (
    format_human as format_language_analysis_human,
)
from vpo.language_analysis import (
    format_json as format_language_analysis_json,
)
from vpo.transcription.interface import (
    MultiLanguageDetectionConfig,
)

logger = logging.getLogger(__name__)


def _get_plugin_registry_or_error():
    """Get a plugin registry with transcription plugins.

    Returns:
        PluginRegistry instance.

    Raises:
        click.ClickException: If no transcription plugin is available.
    """
    from vpo.plugin import get_default_registry
    from vpo.plugin.events import TRANSCRIPTION_REQUESTED

    registry = get_default_registry()

    plugins = registry.get_by_event(TRANSCRIPTION_REQUESTED)
    if not plugins:
        raise click.ClickException(
            "No transcription plugins available.\n"
            "Install a transcription plugin (e.g., whisper-local)."
        )
    return registry


@click.command("inspect")
@click.argument("file", type=click.Path(exists=False))
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["human", "json"]),
    default="human",
    help="Output format (default: human)",
)
@click.option(
    "--analyze-languages",
    "-a",
    is_flag=True,
    help="Analyze audio tracks for multiple languages",
)
@click.option(
    "--show-segments",
    "-s",
    is_flag=True,
    help="Show detailed language segments (requires --analyze-languages)",
)
@click.option(
    "--track",
    "-t",
    type=int,
    default=None,
    help="Analyze only the specified audio track index",
)
@click.option(
    "--classify-tracks",
    "-c",
    is_flag=True,
    help="Classify audio tracks as original/dubbed/commentary",
)
@click.option(
    "--show-acoustic",
    is_flag=True,
    help="Show acoustic profile details (requires --classify-tracks)",
)
def inspect_command(
    file: str,
    output_format: str,
    analyze_languages: bool,
    show_segments: bool,
    track: int | None,
    classify_tracks: bool,
    show_acoustic: bool,
) -> None:
    """Inspect a media file and display track information.

    FILE is the path to the media file to inspect.

    Use --analyze-languages to detect multiple languages in audio tracks.
    This uses speech recognition to sample the audio at multiple positions
    and determine if multiple languages are present.

    Use --classify-tracks to classify audio tracks as original/dubbed or
    commentary based on metadata and acoustic analysis.
    """
    file_path = Path(file)

    # Check if file exists (exit code 1)
    if not file_path.exists():
        click.echo(f"Error: File not found: {file_path}", err=True)
        sys.exit(ExitCode.TARGET_NOT_FOUND)

    # Check ffprobe availability (exit code 2)
    if not FFprobeIntrospector.is_available():
        click.echo(
            "Error: ffprobe is not installed or not in PATH.\n"
            "Install ffmpeg to use media introspection features.",
            err=True,
        )
        sys.exit(ExitCode.FFPROBE_NOT_FOUND)

    try:
        introspector = FFprobeIntrospector()
        result = introspector.get_file_info(file_path)
    except MediaIntrospectionError as e:
        click.echo(f"Error: Could not parse file: {file_path}", err=True)
        click.echo(f"Reason: {e}", err=True)
        sys.exit(ExitCode.PARSE_ERROR)

    # Build output data for JSON format
    output_data: dict[str, Any] | None = None
    if output_format == "json":
        output_data = json.loads(format_json(result))
    else:
        click.echo(format_human(result))

    # Language analysis (if requested)
    language_results: list[tuple[int, LanguageAnalysisResult]] = []
    if analyze_languages:
        # Get audio tracks to analyze
        audio_tracks = [t for t in result.tracks if t.track_type == "audio"]

        if track is not None:
            # Filter to specific track
            audio_tracks = [t for t in audio_tracks if t.index == track]
            if not audio_tracks:
                click.echo(f"Error: No audio track found at index {track}", err=True)
                sys.exit(ExitCode.ANALYSIS_ERROR)

        if not audio_tracks:
            click.echo("No audio tracks to analyze.", err=True)
            sys.exit(ExitCode.SUCCESS)

        # Get plugin registry with transcription plugins
        try:
            plugin_registry = _get_plugin_registry_or_error()
        except click.ClickException as e:
            click.echo(f"Error: {e.message}", err=True)
            sys.exit(ExitCode.ANALYSIS_ERROR)

        # Import adapter for creating per-track transcribers
        from vpo.transcription.coordinator import (
            PluginTranscriberAdapter,
        )

        # Analyze each track
        config = MultiLanguageDetectionConfig(num_samples=5, sample_duration=30.0)

        for audio_track in audio_tracks:
            click.echo(f"\nAnalyzing track {audio_track.index}...", err=True)
            # Use actual track duration if available, else default to 1 hour
            track_duration = audio_track.duration_seconds or 3600.0
            try:
                # Create adapter per-track for thread safety
                transcriber = PluginTranscriberAdapter(
                    registry=plugin_registry,
                    file_path=file_path,
                    track=audio_track,
                )

                # Use a dummy track_id since we're not using the database here
                analysis = analyze_track_languages(
                    file_path=file_path,
                    track_index=audio_track.index,
                    track_id=0,  # Not persisting, so ID doesn't matter
                    track_duration=track_duration,
                    file_hash="",  # Not caching
                    transcriber=transcriber,
                    config=config,
                )
                language_results.append((audio_track.index, analysis))

            except LanguageAnalysisError as e:
                click.echo(
                    f"Warning: Could not analyze track {audio_track.index}: {e}",
                    err=True,
                )

        # Output language analysis results
        if output_format == "json" and output_data is not None:
            output_data["language_analysis"] = {
                f"track_{idx}": format_language_analysis_json(analysis)
                for idx, analysis in language_results
            }
        elif output_format != "json":
            for track_idx, analysis in language_results:
                click.echo(f"\nTrack {track_idx}:")
                click.echo(format_language_analysis_human(analysis, show_segments))

    # Track classification (if requested)
    classification_results: list[dict[str, Any]] = []
    if classify_tracks:
        from vpo.track_classification import (
            detect_commentary,
            determine_original_track,
        )

        # Get audio tracks to classify
        audio_tracks = [t for t in result.tracks if t.track_type == "audio"]

        if not audio_tracks:
            click.echo("No audio tracks to classify.", err=True)
        else:
            # Try to determine original language from metadata
            original_language = None

            # Build language analysis dict for determine_original_track
            lang_analysis_dict = None
            if language_results:
                lang_analysis_dict = {
                    idx: analysis for idx, analysis in language_results
                }

            # Determine which track is likely the original
            original_track_id, detection_method, confidence = determine_original_track(
                audio_tracks=audio_tracks,
                original_language=original_language,
                language_analysis=lang_analysis_dict,
            )

            for audio_track in audio_tracks:
                track_result: dict[str, Any] = {
                    "index": audio_track.index,
                    "language": audio_track.language or "und",
                    "title": audio_track.title,
                }

                # Classify original/dubbed
                is_original = original_track_id == audio_track.index
                track_result["original_dubbed"] = (
                    "original" if is_original else "dubbed"
                )
                track_result["original_confidence"] = (
                    confidence if is_original else 1.0 - confidence
                )

                # Classify commentary
                is_commentary, commentary_source = detect_commentary(
                    track=audio_track,
                    acoustic_profile=None,  # Would need acoustic analyzer
                )
                track_result["is_commentary"] = is_commentary
                track_result["commentary_source"] = commentary_source

                track_result["detection_method"] = detection_method.value

                classification_results.append(track_result)

            # Output classification results
            if output_format == "json" and output_data is not None:
                output_data["track_classification"] = classification_results
            else:
                click.echo("\nTrack Classification:")
                click.echo("=" * 60)
                click.echo(
                    f"{'Track':<6} {'Lang':<6} {'Type':<10} {'Commentary':<12} "
                    f"{'Conf':<6} {'Method'}"
                )
                click.echo("-" * 60)

                for tc in classification_results:
                    od_type = tc["original_dubbed"]
                    commentary = "yes" if tc["is_commentary"] else "no"

                    # Color coding
                    od_color = "green" if od_type == "original" else "yellow"
                    cm_color = "cyan" if tc["is_commentary"] else "white"

                    conf_str = f"{tc['original_confidence']:.0%}"
                    click.echo(
                        f"{tc['index']:<6} "
                        f"{tc['language']:<6} "
                        f"{click.style(od_type, fg=od_color):<10} "
                        f"{click.style(commentary, fg=cm_color):<12} "
                        f"{conf_str:<6} "
                        f"{tc['detection_method']}"
                    )

                # Show acoustic profile if requested
                if show_acoustic:
                    click.echo("\nNote: Acoustic profile analysis not available")
                    click.echo(
                        "(requires transcription plugin with acoustic_analysis feature)"
                    )

    # Output JSON at the end (consolidates all JSON output in one place)
    if output_format == "json" and output_data is not None:
        click.echo(json.dumps(output_data, indent=2))
