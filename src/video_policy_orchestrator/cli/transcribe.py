"""CLI commands for audio transcription and language detection."""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import click

from video_policy_orchestrator.db.models import (
    TranscriptionResultRecord,
    get_file_by_path,
    get_tracks_for_file,
    get_transcription_result,
    upsert_transcription_result,
)
from video_policy_orchestrator.transcription.audio_extractor import (
    extract_audio_stream,
    get_file_duration,
)
from video_policy_orchestrator.transcription.interface import TranscriptionError
from video_policy_orchestrator.transcription.models import detect_commentary_type
from video_policy_orchestrator.transcription.multi_sample import (
    AggregatedResult,
    MultiSampleConfig,
    smart_detect,
)
from video_policy_orchestrator.transcription.service import (
    TranscriptionSetupError,
    prepare_transcription_context,
    should_skip_track,
)

logger = logging.getLogger(__name__)


@click.group(name="transcribe")
def transcribe_group() -> None:
    """Audio transcription and language detection commands."""
    pass


@transcribe_group.command(name="detect")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--force",
    is_flag=True,
    help="Re-run detection even if results already exist",
)
@click.option(
    "--plugin",
    type=str,
    default=None,
    help="Transcription plugin to use (default: auto-detect)",
)
@click.option(
    "--update",
    "-u",
    is_flag=True,
    help="Update language tags in file after detection",
)
@click.option(
    "--threshold",
    type=float,
    default=0.8,
    help="Minimum confidence threshold for language updates (default: 0.8)",
)
@click.option(
    "--dry-run",
    "-n",
    is_flag=True,
    help="Show what would be updated without making changes",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results in JSON format",
)
@click.option(
    "--samples",
    type=int,
    default=3,
    help="Maximum number of audio samples to analyze (default: 3)",
)
@click.option(
    "--sample-duration",
    type=int,
    default=30,
    help="Duration of each audio sample in seconds (default: 30)",
)
@click.option(
    "--confidence-threshold",
    type=float,
    default=0.85,
    help="Confidence level to stop sampling early (default: 0.85)",
)
@click.pass_context
def detect_command(
    ctx: click.Context,
    path: Path,
    force: bool,
    plugin: str | None,
    update: bool,
    threshold: float,
    dry_run: bool,
    output_json: bool,
    samples: int,
    sample_duration: int,
    confidence_threshold: float,
) -> None:
    """Detect spoken language in audio tracks with full transcription.

    Performs full transcription to detect language and extract a transcript
    sample. This is more accurate but slower than 'quick' detection.

    Use --update to apply detected languages to the file's metadata.
    Use --dry-run with --update to preview changes without applying them.

    PATH is the path to a video file to analyze.
    """
    # Use service layer for setup and validation
    conn: sqlite3.Connection | None = ctx.obj.get("db_conn")
    try:
        context = prepare_transcription_context(conn, path, plugin)
    except TranscriptionSetupError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    transcriber = context.transcriber
    file_record = context.file_record
    audio_tracks = context.audio_tracks

    results = []

    # Get file duration for multi-sample detection
    try:
        file_duration = get_file_duration(Path(file_record.path))
        logger.debug("File duration: %.1f seconds", file_duration)
    except TranscriptionError as e:
        logger.warning("Could not determine file duration: %s", e)
        file_duration = 0.0  # Will fall back to single sample

    # Create multi-sample config from CLI options
    multi_sample_config = MultiSampleConfig(
        max_samples=samples,
        sample_duration=sample_duration,
        confidence_threshold=confidence_threshold,
    )

    for track in audio_tracks:
        # Check for existing result using service layer
        skip, existing = should_skip_track(context.conn, track, force)
        if skip and existing:
            if output_json:
                results.append(_format_result_json(track, existing, skipped=True))
            else:
                click.echo(
                    f"Track {track.track_index} ({track.codec}): "
                    f"Already detected - {existing.detected_language} "
                    f"({existing.confidence_score:.1%} confidence). "
                    f"Use --force to re-run."
                )
            continue

        if not output_json:
            click.echo(f"Processing track {track.track_index} ({track.codec})...")

        # Use incumbent language from track metadata for bias
        incumbent_language = track.language if track.language != "und" else None

        # Perform multi-sample smart detection
        try:
            logger.info(
                "Starting multi-sample detection",
                extra={
                    "file": str(path),
                    "track_index": track.track_index,
                    "codec": track.codec,
                    "max_samples": samples,
                    "incumbent_language": incumbent_language,
                },
            )
            aggregated = smart_detect(
                file_path=Path(file_record.path),
                track_index=track.track_index,
                track_duration=file_duration,
                transcriber=transcriber,
                config=multi_sample_config,
                incumbent_language=incumbent_language,
            )
            logger.info(
                "Multi-sample detection complete",
                extra={
                    "track_index": track.track_index,
                    "detected_language": aggregated.language,
                    "confidence": aggregated.confidence,
                    "samples_taken": aggregated.samples_taken,
                },
            )
        except TranscriptionError as e:
            logger.warning(
                "Multi-sample detection failed",
                extra={
                    "file": str(path),
                    "track_index": track.track_index,
                    "error": str(e),
                },
            )
            if output_json:
                results.append(
                    {
                        "track_index": track.track_index,
                        "codec": track.codec,
                        "error": str(e),
                    }
                )
            else:
                click.echo(f"  Error during detection: {e}", err=True)
            continue

        # Determine track type from metadata and transcript
        track_type = detect_commentary_type(track.title, aggregated.transcript_sample)

        # Store result
        now = datetime.now(timezone.utc).isoformat()
        record = TranscriptionResultRecord(
            id=None,
            track_id=track.id,
            detected_language=aggregated.language,
            confidence_score=aggregated.confidence,
            track_type=track_type.value,
            transcript_sample=aggregated.transcript_sample,
            plugin_name=transcriber.name,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        try:
            upsert_transcription_result(context.conn, record)
        except sqlite3.Error as e:
            logger.error(
                "Failed to store transcription result",
                extra={"track_id": track.id, "error": str(e)},
            )
            click.echo(f"  Warning: Failed to save result to database: {e}", err=True)
            continue
        logger.debug(
            "Transcription result stored",
            extra={"track_id": track.id, "track_index": track.track_index},
        )

        if output_json:
            results.append(
                _format_result_json_with_samples(
                    track, record, aggregated, skipped=False
                )
            )
        else:
            # Display result
            current_lang = track.language or "und"
            detected_lang = aggregated.language or "unknown"
            confidence = aggregated.confidence

            click.echo(f"  Current language: {current_lang}")
            click.echo(
                f"  Detected language: {detected_lang} "
                f"({confidence:.1%}, {aggregated.samples_taken} sample(s))"
            )

            # Show individual sample details if multiple samples taken
            if aggregated.samples_taken > 1:
                for i, sample in enumerate(aggregated.sample_results, 1):
                    click.echo(
                        f"    Sample {i} @ {sample.position:.0f}s: "
                        f"{sample.language} ({sample.confidence:.1%})"
                    )

            if current_lang != detected_lang and current_lang != "und":
                click.echo(
                    "  Note: Current and detected languages differ. "
                    "Use --update to apply detected language."
                )

    if output_json:
        click.echo(json.dumps({"file": str(path), "tracks": results}, indent=2))

    # Handle --update flag to apply detected languages
    if update:
        updates_to_apply = []

        # Collect tracks that need updating
        for track in audio_tracks:
            tr_result = get_transcription_result(conn, track.id)
            if tr_result is None:
                continue

            # Check confidence threshold
            if tr_result.confidence_score < threshold:
                if not output_json:
                    click.echo(
                        f"Skipping track {track.track_index}: "
                        f"confidence {tr_result.confidence_score:.1%} "
                        f"below threshold {threshold:.1%}"
                    )
                continue

            # Check if update is needed
            current_lang = track.language or "und"
            detected_lang = tr_result.detected_language

            if detected_lang and current_lang != detected_lang:
                updates_to_apply.append(
                    {
                        "track": track,
                        "current": current_lang,
                        "detected": detected_lang,
                        "confidence": tr_result.confidence_score,
                    }
                )

        if not updates_to_apply:
            if not output_json:
                click.echo("\nNo language updates needed.")
            return

        if not output_json:
            click.echo(f"\nLanguage updates ({len(updates_to_apply)} track(s)):")
            for u in updates_to_apply:
                click.echo(
                    f"  Track {u['track'].track_index}: "
                    f"{u['current']} → {u['detected']} ({u['confidence']:.1%})"
                )

        if dry_run:
            if not output_json:
                click.echo("\n[Dry-run mode - no changes applied]")
            return

        # Apply updates using mkvpropedit
        _apply_language_updates(path, updates_to_apply, output_json)


@transcribe_group.command(name="quick")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--force",
    is_flag=True,
    help="Re-run detection even if results already exist",
)
@click.option(
    "--plugin",
    type=str,
    default=None,
    help="Transcription plugin to use (default: auto-detect)",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results in JSON format",
)
@click.pass_context
def quick_command(
    ctx: click.Context,
    path: Path,
    force: bool,
    plugin: str | None,
    output_json: bool,
) -> None:
    """Quick language detection without full transcription.

    Performs fast language-only detection by analyzing a 30-second audio
    sample. This is faster than 'detect' but does not extract transcript
    samples.

    Use 'vpo transcribe detect' for full transcription with samples.

    PATH is the path to a video file to analyze.
    """
    # Use service layer for setup and validation
    conn: sqlite3.Connection | None = ctx.obj.get("db_conn")
    try:
        context = prepare_transcription_context(conn, path, plugin)
    except TranscriptionSetupError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    transcriber = context.transcriber
    file_record = context.file_record
    audio_tracks = context.audio_tracks

    results = []

    for track in audio_tracks:
        # Check for existing result using service layer
        skip, existing = should_skip_track(context.conn, track, force)
        if skip and existing:
            if output_json:
                results.append(_format_result_json(track, existing, skipped=True))
            else:
                click.echo(
                    f"Track {track.track_index} ({track.codec}): "
                    f"Already detected - {existing.detected_language} "
                    f"({existing.confidence_score:.1%} confidence). "
                    f"Use --force to re-run."
                )
            continue

        # Extract audio
        try:
            if not output_json:
                click.echo(f"Processing track {track.track_index} ({track.codec})...")

            logger.info(
                "Extracting audio for quick language detection",
                extra={
                    "file": str(path),
                    "track_index": track.track_index,
                    "codec": track.codec,
                },
            )
            audio_data = extract_audio_stream(
                Path(file_record.path),
                track.track_index,
            )
        except TranscriptionError as e:
            logger.warning(
                "Audio extraction failed",
                extra={
                    "file": str(path),
                    "track_index": track.track_index,
                    "error": str(e),
                },
            )
            if output_json:
                results.append(
                    {
                        "track_index": track.track_index,
                        "codec": track.codec,
                        "error": str(e),
                    }
                )
            else:
                click.echo(f"  Error extracting audio: {e}", err=True)
            continue

        # Quick language detection (no full transcription)
        try:
            logger.debug(
                "Running quick language detection",
                extra={"plugin": transcriber.name, "track_index": track.track_index},
            )
            result = transcriber.detect_language(audio_data)
            logger.info(
                "Quick language detection complete",
                extra={
                    "track_index": track.track_index,
                    "detected_language": result.detected_language,
                    "confidence": result.confidence_score,
                    "track_type": result.track_type.value,
                },
            )
        except TranscriptionError as e:
            logger.warning(
                "Language detection failed",
                extra={
                    "file": str(path),
                    "track_index": track.track_index,
                    "error": str(e),
                },
            )
            if output_json:
                results.append(
                    {
                        "track_index": track.track_index,
                        "codec": track.codec,
                        "error": str(e),
                    }
                )
            else:
                click.echo(f"  Error detecting language: {e}", err=True)
            continue

        # Store result (no transcript_sample for quick detection)
        now = datetime.now(timezone.utc).isoformat()
        record = TranscriptionResultRecord(
            id=None,
            track_id=track.id,
            detected_language=result.detected_language,
            confidence_score=result.confidence_score,
            track_type=result.track_type.value,
            transcript_sample=None,  # Quick detection doesn't extract samples
            plugin_name=transcriber.name,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        try:
            upsert_transcription_result(context.conn, record)
        except sqlite3.Error as e:
            logger.error(
                "Failed to store quick detection result",
                extra={"track_id": track.id, "error": str(e)},
            )
            click.echo(f"  Warning: Failed to save result to database: {e}", err=True)
            continue
        logger.debug(
            "Quick detection result stored",
            extra={"track_id": track.id, "track_index": track.track_index},
        )

        if output_json:
            results.append(_format_result_json(track, record, skipped=False))
        else:
            # Display result
            current_lang = track.language or "und"
            detected_lang = result.detected_language or "unknown"
            confidence = result.confidence_score

            click.echo(f"  Current language: {current_lang}")
            click.echo(f"  Detected language: {detected_lang} ({confidence:.1%})")

    if output_json:
        click.echo(json.dumps({"file": str(path), "tracks": results}, indent=2))


def _format_result_json(
    track, result: TranscriptionResultRecord, skipped: bool
) -> dict:
    """Format a detection result for JSON output."""
    return {
        "track_index": track.track_index,
        "codec": track.codec,
        "current_language": track.language,
        "detected_language": result.detected_language,
        "confidence_score": result.confidence_score,
        "track_type": result.track_type,
        "plugin_name": result.plugin_name,
        "skipped": skipped,
    }


def _format_result_json_with_samples(
    track,
    result: TranscriptionResultRecord,
    aggregated: AggregatedResult,
    skipped: bool,
) -> dict:
    """Format a detection result with sample details for JSON output."""
    output = {
        "track_index": track.track_index,
        "codec": track.codec,
        "current_language": track.language,
        "detected_language": result.detected_language,
        "confidence_score": result.confidence_score,
        "track_type": result.track_type,
        "plugin_name": result.plugin_name,
        "skipped": skipped,
        "samples_taken": aggregated.samples_taken,
    }

    # Include individual sample details
    if aggregated.sample_results:
        output["samples"] = [
            {
                "position": sample.position,
                "language": sample.language,
                "confidence": sample.confidence,
            }
            for sample in aggregated.sample_results
        ]

    return output


def _apply_language_updates(path: Path, updates: list[dict], output_json: bool) -> None:
    """Apply language updates to file using mkvpropedit.

    Args:
        path: Path to the media file.
        updates: List of update dicts with 'track', 'detected' keys.
        output_json: Whether to output in JSON format.
    """
    from video_policy_orchestrator.executor.mkvpropedit import MkvPropEditExecutor
    from video_policy_orchestrator.policy.models import ActionType, PlannedAction

    executor = MkvPropEditExecutor()

    # Check if mkvpropedit is available
    if not executor.is_available():
        click.echo(
            "Error: mkvpropedit not found. "
            "Install mkvtoolnix to apply language updates.",
            err=True,
        )
        raise SystemExit(1)

    # Check container format
    if path.suffix.lower() not in (".mkv", ".mka", ".mks"):
        click.echo(
            f"Error: Language updates only supported for MKV files. Got: {path.suffix}",
            err=True,
        )
        raise SystemExit(1)

    # Create planned actions for the executor
    actions = []
    for u in updates:
        actions.append(
            PlannedAction(
                action_type=ActionType.SET_LANGUAGE,
                track_index=u["track"].track_index,
                current_value=u["current"],
                desired_value=u["detected"],
            )
        )

    # Execute updates
    try:
        executor.execute(path, actions)
        if not output_json:
            click.echo(f"\nApplied {len(actions)} language update(s) successfully.")
    except Exception as e:
        click.echo(f"Error applying updates: {e}", err=True)
        raise SystemExit(1)


@transcribe_group.command(name="status")
@click.argument("path", type=click.Path(exists=True, path_type=Path), required=False)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results in JSON format",
)
@click.pass_context
def status_command(
    ctx: click.Context,
    path: Path | None,
    output_json: bool,
) -> None:
    """Show transcription status for files.

    If PATH is provided, shows status for that specific file.
    Otherwise, shows library-wide transcription overview.
    """
    conn: sqlite3.Connection | None = ctx.obj.get("db_conn")
    if conn is None:
        click.echo("Error: Database connection not available", err=True)
        raise SystemExit(1)

    if path:
        _show_file_status(conn, path, output_json)
    else:
        _show_library_status(conn, output_json)


def _show_file_status(conn: sqlite3.Connection, path: Path, output_json: bool) -> None:
    """Show transcription status for a specific file."""
    file_record = get_file_by_path(conn, str(path.resolve()))
    if file_record is None:
        click.echo(f"Error: File not found in database: {path}", err=True)
        raise SystemExit(1)

    tracks = get_tracks_for_file(conn, file_record.id)
    audio_tracks = [t for t in tracks if t.track_type == "audio"]

    results = []
    for track in audio_tracks:
        result = get_transcription_result(conn, track.id)
        results.append(
            {
                "track_index": track.track_index,
                "codec": track.codec,
                "current_language": track.language,
                "has_transcription": result is not None,
                "detected_language": result.detected_language if result else None,
                "confidence_score": result.confidence_score if result else None,
                "plugin_name": result.plugin_name if result else None,
            }
        )

    if output_json:
        click.echo(json.dumps({"file": str(path), "tracks": results}, indent=2))
    else:
        click.echo(f"File: {path}")
        click.echo(f"Audio tracks: {len(audio_tracks)}")
        transcribed = sum(1 for r in results if r["has_transcription"])
        click.echo(f"Transcribed: {transcribed}/{len(audio_tracks)}")
        click.echo()

        for r in results:
            status = "detected" if r["has_transcription"] else "pending"
            lang = r["detected_language"] or r["current_language"] or "und"
            conf = f" ({r['confidence_score']:.1%})" if r["confidence_score"] else ""
            click.echo(
                f"  Track {r['track_index']} ({r['codec']}): {lang}{conf} [{status}]"
            )


def _show_library_status(conn: sqlite3.Connection, output_json: bool) -> None:
    """Show library-wide transcription status."""
    # Count total audio tracks
    cursor = conn.execute("SELECT COUNT(*) FROM tracks WHERE track_type = 'audio'")
    total_audio = cursor.fetchone()[0]

    # Count tracks with transcription results
    cursor = conn.execute(
        """
        SELECT COUNT(DISTINCT t.id)
        FROM tracks t
        JOIN transcription_results tr ON t.id = tr.track_id
        WHERE t.track_type = 'audio'
        """
    )
    transcribed = cursor.fetchone()[0]

    # Count by detected language
    cursor = conn.execute(
        """
        SELECT detected_language, COUNT(*) as count
        FROM transcription_results
        GROUP BY detected_language
        ORDER BY count DESC
        LIMIT 10
        """
    )
    language_counts = [
        {"language": row[0] or "unknown", "count": row[1]} for row in cursor.fetchall()
    ]

    if output_json:
        click.echo(
            json.dumps(
                {
                    "total_audio_tracks": total_audio,
                    "transcribed_tracks": transcribed,
                    "pending_tracks": total_audio - transcribed,
                    "languages": language_counts,
                },
                indent=2,
            )
        )
    else:
        click.echo("Library Transcription Status")
        click.echo("=" * 30)
        click.echo(f"Total audio tracks: {total_audio}")
        click.echo(f"Transcribed: {transcribed}")
        click.echo(f"Pending: {total_audio - transcribed}")
        if language_counts:
            click.echo()
            click.echo("Detected languages:")
            for lc in language_counts:
                click.echo(f"  {lc['language']}: {lc['count']}")


@transcribe_group.command(name="clear")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
@click.pass_context
def clear_command(
    ctx: click.Context,
    path: Path,
    yes: bool,
) -> None:
    """Clear transcription results for a file.

    Removes all transcription results associated with the specified file,
    allowing them to be re-detected.
    """
    from video_policy_orchestrator.db.models import (
        delete_transcription_results_for_file,
    )

    conn: sqlite3.Connection | None = ctx.obj.get("db_conn")
    if conn is None:
        click.echo("Error: Database connection not available", err=True)
        raise SystemExit(1)

    file_record = get_file_by_path(conn, str(path.resolve()))
    if file_record is None:
        click.echo(f"Error: File not found in database: {path}", err=True)
        raise SystemExit(1)

    if not yes:
        click.confirm(
            f"Clear all transcription results for {path.name}?",
            abort=True,
        )

    deleted = delete_transcription_results_for_file(conn, file_record.id)
    click.echo(f"Cleared {deleted} transcription result(s)")
