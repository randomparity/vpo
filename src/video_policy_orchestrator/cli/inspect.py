"""CLI inspect command for Video Policy Orchestrator."""

import json
import logging
import sys
from pathlib import Path
from typing import Any

import click

from video_policy_orchestrator.db.models import IntrospectionResult, TrackInfo
from video_policy_orchestrator.introspector.ffprobe import FFprobeIntrospector
from video_policy_orchestrator.introspector.interface import MediaIntrospectionError
from video_policy_orchestrator.language_analysis import (
    LanguageAnalysisError,
    LanguageAnalysisResult,
    LanguageClassification,
    analyze_track_languages,
)
from video_policy_orchestrator.transcription.interface import (
    MultiLanguageDetectionConfig,
)

logger = logging.getLogger(__name__)

# Exit codes per cli-inspect.md contract
EXIT_SUCCESS = 0
EXIT_FILE_NOT_FOUND = 1
EXIT_FFPROBE_NOT_INSTALLED = 2
EXIT_PARSE_ERROR = 3
EXIT_ANALYSIS_ERROR = 4


def format_human(result: IntrospectionResult) -> str:
    """Format introspection result for human-readable output.

    Args:
        result: The introspection result to format.

    Returns:
        Formatted string for terminal output.
    """
    lines: list[str] = []

    # File info header
    lines.append(f"File: {result.file_path}")
    if result.container_format:
        # Make container format more readable
        container = result.container_format.split(",")[0].title()
        lines.append(f"Container: {container}")
    lines.append("")

    # Group tracks by type
    video_tracks = [t for t in result.tracks if t.track_type == "video"]
    audio_tracks = [t for t in result.tracks if t.track_type == "audio"]
    subtitle_tracks = [t for t in result.tracks if t.track_type == "subtitle"]
    other_tracks = [
        t for t in result.tracks if t.track_type not in ("video", "audio", "subtitle")
    ]

    lines.append("Tracks:")

    if video_tracks:
        lines.append("  Video:")
        for track in video_tracks:
            lines.append(f"    {_format_track_line(track)}")

    if audio_tracks:
        lines.append("  Audio:")
        for track in audio_tracks:
            lines.append(f"    {_format_track_line(track)}")

    if subtitle_tracks:
        lines.append("  Subtitles:")
        for track in subtitle_tracks:
            lines.append(f"    {_format_track_line(track)}")

    if other_tracks:
        lines.append("  Other:")
        for track in other_tracks:
            lines.append(f"    {_format_track_line(track)}")

    if not result.tracks:
        lines.append("  (no tracks found)")

    # Add warnings if any
    if result.warnings:
        lines.append("")
        lines.append("Warnings:")
        for warning in result.warnings:
            lines.append(f"  - {warning}")

    return "\n".join(lines)


def _format_track_line(track: TrackInfo) -> str:
    """Format a single track for human output.

    Args:
        track: The track to format.

    Returns:
        Formatted track line.
    """
    parts = [f"#{track.index}", f"[{track.track_type}]"]

    if track.codec:
        parts.append(track.codec)

    # Video-specific: resolution and frame rate
    if track.track_type == "video":
        if track.width and track.height:
            parts.append(f"{track.width}x{track.height}")
        if track.frame_rate:
            # Convert frame rate to decimal for display
            fps = _frame_rate_to_fps(track.frame_rate)
            if fps:
                parts.append(f"@ {fps}fps")

    # Audio-specific: channel layout and language
    if track.track_type == "audio":
        if track.channel_layout:
            parts.append(track.channel_layout)

    # Language (for audio/subtitle)
    if track.language and track.language != "und":
        parts.append(track.language)

    # Title in quotes
    if track.title:
        parts.append(f'"{track.title}"')

    # Flags
    flags = []
    if track.is_default:
        flags.append("default")
    if track.is_forced:
        flags.append("forced")
    if flags:
        parts.append(f"({', '.join(flags)})")

    return " ".join(parts)


def _frame_rate_to_fps(frame_rate: str) -> str | None:
    """Convert frame rate string to decimal FPS.

    Args:
        frame_rate: Frame rate as "N/D" or decimal string.

    Returns:
        Formatted FPS string or None if invalid.
    """
    try:
        if "/" in frame_rate:
            num, denom = frame_rate.split("/")
            fps = int(num) / int(denom)
        else:
            fps = float(frame_rate)

        # Format nicely (e.g., 23.976 or 30)
        if fps == int(fps):
            return str(int(fps))
        return f"{fps:.3f}".rstrip("0").rstrip(".")
    except (ValueError, ZeroDivisionError):
        return None


def format_json(result: IntrospectionResult) -> str:
    """Format introspection result as JSON.

    Args:
        result: The introspection result to format.

    Returns:
        JSON string.
    """
    data = {
        "file": str(result.file_path),
        "container": result.container_format,
        "tracks": [_track_to_dict(t) for t in result.tracks],
        "warnings": result.warnings,
    }
    return json.dumps(data, indent=2)


def _track_to_dict(track: TrackInfo) -> dict[str, Any]:
    """Convert TrackInfo to JSON-serializable dict.

    Args:
        track: The track to convert.

    Returns:
        Dictionary representation.
    """
    d: dict[str, Any] = {
        "index": track.index,
        "type": track.track_type,
        "codec": track.codec,
        "language": track.language,
        "title": track.title,
        "is_default": track.is_default,
        "is_forced": track.is_forced,
    }

    # Add video fields if present
    if track.width is not None:
        d["width"] = track.width
    if track.height is not None:
        d["height"] = track.height
    if track.frame_rate is not None:
        d["frame_rate"] = track.frame_rate

    # Add audio fields if present
    if track.channels is not None:
        d["channels"] = track.channels
    if track.channel_layout is not None:
        d["channel_layout"] = track.channel_layout

    return d


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


def _get_transcriber():
    """Get a transcription plugin for language analysis.

    Returns:
        TranscriptionPlugin instance.

    Raises:
        click.ClickException: If no transcription plugin is available.
    """
    try:
        from video_policy_orchestrator.plugins.whisper_transcriber.plugin import (
            WhisperTranscriptionPlugin,
        )

        return WhisperTranscriptionPlugin()
    except Exception as e:
        raise click.ClickException(
            f"Could not initialize transcription plugin: {e}\n"
            "Make sure openai-whisper is installed: pip install openai-whisper"
        )


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

    # Output result
    if output_format == "json":
        output_data: dict[str, Any] = json.loads(format_json(result))
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
            transcriber = _get_transcriber()
        except click.ClickException as e:
            click.echo(f"Error: {e.message}", err=True)
            sys.exit(EXIT_ANALYSIS_ERROR)

        # Get file duration from introspection
        # (estimate from first video track or use default)
        file_duration = 3600.0  # Default 1 hour
        video_tracks = [t for t in result.tracks if t.track_type == "video"]
        if video_tracks and video_tracks[0].frame_rate:
            # Could calculate from frame rate, but for now use default
            pass

        # Analyze each track
        config = MultiLanguageDetectionConfig(num_samples=5, sample_duration=30.0)

        for audio_track in audio_tracks:
            click.echo(f"\nAnalyzing track {audio_track.index}...", err=True)
            try:
                # Use a dummy track_id since we're not using the database here
                analysis = analyze_track_languages(
                    file_path=file_path,
                    track_index=audio_track.index,
                    track_id=0,  # Not persisting, so ID doesn't matter
                    track_duration=file_duration,
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

        # Output language analysis
        if output_format == "json":
            output_data["language_analysis"] = {
                f"track_{idx}": format_language_analysis_json(analysis)
                for idx, analysis in language_results
            }
            click.echo(json.dumps(output_data, indent=2))
        else:
            for track_idx, analysis in language_results:
                click.echo(f"\nTrack {track_idx}:")
                click.echo(format_language_analysis_human(analysis, show_segments))
    elif output_format == "json":
        click.echo(json.dumps(output_data, indent=2))

    sys.exit(EXIT_SUCCESS)
