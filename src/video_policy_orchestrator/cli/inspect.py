"""CLI inspect command for Video Policy Orchestrator."""

import json
import logging
import sys
from pathlib import Path
from typing import Any

import click

from video_policy_orchestrator.cli.exit_codes import INSPECT_EXIT_CODES
from video_policy_orchestrator.introspector import (
    FFprobeIntrospector,
    MediaIntrospectionError,
    format_human,
    format_json,
)
from video_policy_orchestrator.language_analysis import (
    LanguageAnalysisError,
    LanguageAnalysisResult,
    LanguageClassification,
    analyze_track_languages,
)
from video_policy_orchestrator.transcription.factory import get_transcriber
from video_policy_orchestrator.transcription.interface import (
    MultiLanguageDetectionConfig,
)

logger = logging.getLogger(__name__)

# Backward compatibility aliases - prefer using ExitCode or INSPECT_EXIT_CODES
EXIT_SUCCESS = INSPECT_EXIT_CODES["EXIT_SUCCESS"]
EXIT_FILE_NOT_FOUND = INSPECT_EXIT_CODES["EXIT_FILE_NOT_FOUND"]
EXIT_FFPROBE_NOT_INSTALLED = INSPECT_EXIT_CODES["EXIT_FFPROBE_NOT_INSTALLED"]
EXIT_PARSE_ERROR = INSPECT_EXIT_CODES["EXIT_PARSE_ERROR"]
EXIT_ANALYSIS_ERROR = INSPECT_EXIT_CODES["EXIT_ANALYSIS_ERROR"]


def format_language_analysis_human(
    analysis: LanguageAnalysisResult,
    show_segments: bool = False,
) -> str:
    """Format language analysis result for human-readable output.

    Args:
        analysis: The language analysis result to format.
        show_segments: Whether to show detailed segment information.

    Returns:
        Formatted string for terminal output.
    """
    lines: list[str] = []

    # Classification header
    if analysis.classification == LanguageClassification.MULTI_LANGUAGE:
        lines.append("Language Analysis: MULTI-LANGUAGE")
    else:
        lines.append("Language Analysis: SINGLE-LANGUAGE")

    # Primary language
    lines.append(
        f"  Primary: {analysis.primary_language} "
        f"({analysis.primary_percentage * 100:.1f}%)"
    )

    # Secondary languages
    if analysis.secondary_languages:
        lines.append("  Secondary:")
        for lang_pct in analysis.secondary_languages:
            lines.append(
                f"    - {lang_pct.language_code}: {lang_pct.percentage * 100:.1f}%"
            )

    # Metadata
    lines.append(
        f"  Analysis: {len(analysis.segments)} samples, "
        f"{analysis.metadata.speech_ratio * 100:.0f}% speech detected"
    )

    # Segments detail (if requested)
    if show_segments and analysis.segments:
        lines.append("")
        lines.append("  Segments:")
        for seg in analysis.segments:
            lines.append(
                f"    {seg.start_time:.1f}s-{seg.end_time:.1f}s: "
                f"{seg.language_code} (confidence: {seg.confidence:.2f})"
            )

    return "\n".join(lines)


def format_language_analysis_json(analysis: LanguageAnalysisResult) -> dict[str, Any]:
    """Format language analysis result for JSON output.

    Args:
        analysis: The language analysis result to format.

    Returns:
        Dictionary representation for JSON serialization.
    """
    return {
        "classification": analysis.classification.value,
        "primary_language": analysis.primary_language,
        "primary_percentage": analysis.primary_percentage,
        "secondary_languages": [
            {"code": lp.language_code, "percentage": lp.percentage}
            for lp in analysis.secondary_languages
        ],
        "is_multi_language": analysis.is_multi_language,
        "segments": [
            {
                "language": seg.language_code,
                "start_time": seg.start_time,
                "end_time": seg.end_time,
                "confidence": seg.confidence,
            }
            for seg in analysis.segments
        ],
        "metadata": {
            "plugin": analysis.metadata.plugin_name,
            "model": analysis.metadata.model_name,
            "samples": len(analysis.metadata.sample_positions),
            "speech_ratio": analysis.metadata.speech_ratio,
        },
    }


def _get_transcriber_or_error():
    """Get a transcription plugin for language analysis.

    Returns:
        TranscriptionPlugin instance or None if unavailable.

    Raises:
        click.ClickException: If no transcription plugin is available.
    """
    transcriber = get_transcriber(require_multi_language=True)
    if transcriber is None:
        raise click.ClickException(
            "Could not initialize transcription plugin.\n"
            "Make sure openai-whisper is installed: pip install openai-whisper"
        )
    return transcriber


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
def inspect_command(
    file: str,
    output_format: str,
    analyze_languages: bool,
    show_segments: bool,
    track: int | None,
) -> None:
    """Inspect a media file and display track information.

    FILE is the path to the media file to inspect.

    Use --analyze-languages to detect multiple languages in audio tracks.
    This uses speech recognition to sample the audio at multiple positions
    and determine if multiple languages are present.
    """
    file_path = Path(file)

    # Check if file exists (exit code 1)
    if not file_path.exists():
        click.echo(f"Error: File not found: {file_path}", err=True)
        sys.exit(EXIT_FILE_NOT_FOUND)

    # Check ffprobe availability (exit code 2)
    if not FFprobeIntrospector.is_available():
        click.echo(
            "Error: ffprobe is not installed or not in PATH.\n"
            "Install ffmpeg to use media introspection features.",
            err=True,
        )
        sys.exit(EXIT_FFPROBE_NOT_INSTALLED)

    try:
        introspector = FFprobeIntrospector()
        result = introspector.get_file_info(file_path)
    except MediaIntrospectionError as e:
        click.echo(f"Error: Could not parse file: {file_path}", err=True)
        click.echo(f"Reason: {e}", err=True)
        sys.exit(EXIT_PARSE_ERROR)

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
                sys.exit(EXIT_ANALYSIS_ERROR)

        if not audio_tracks:
            click.echo("No audio tracks to analyze.", err=True)
            sys.exit(EXIT_SUCCESS)

        # Get transcriber plugin
        try:
            transcriber = _get_transcriber_or_error()
        except click.ClickException as e:
            click.echo(f"Error: {e.message}", err=True)
            sys.exit(EXIT_ANALYSIS_ERROR)

        # Analyze each track
        config = MultiLanguageDetectionConfig(num_samples=5, sample_duration=30.0)

        for audio_track in audio_tracks:
            click.echo(f"\nAnalyzing track {audio_track.index}...", err=True)
            # Use actual track duration if available, else default to 1 hour
            track_duration = audio_track.duration_seconds or 3600.0
            try:
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

    # Output JSON at the end (consolidates all JSON output in one place)
    if output_format == "json" and output_data is not None:
        click.echo(json.dumps(output_data, indent=2))

    sys.exit(EXIT_SUCCESS)
