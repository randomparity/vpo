"""Scan command for VPO CLI."""

import json
import sys
from pathlib import Path

import click

from video_policy_orchestrator.scanner.orchestrator import (
    DEFAULT_EXTENSIONS,
    ScannerOrchestrator,
)


class ProgressDisplay:
    """Display progress for scan operations.

    Shows simple counters that update in place using carriage return.
    Only active when output is a TTY and not JSON mode.
    """

    def __init__(self, *, enabled: bool = True):
        """Initialize the progress display.

        Args:
            enabled: Whether to show progress output.
        """
        self._enabled = enabled and sys.stdout.isatty()
        self._phase = ""
        self._last_line_len = 0

    def _write(self, text: str) -> None:
        """Write text to stdout, clearing previous line."""
        if not self._enabled:
            return
        # Clear previous line and write new text
        clear = "\r" + " " * self._last_line_len + "\r"
        sys.stdout.write(clear + text)
        sys.stdout.flush()
        self._last_line_len = len(text)

    def _finish_line(self) -> None:
        """Finish current line with newline."""
        if self._enabled and self._last_line_len > 0:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._last_line_len = 0

    def on_discover_progress(self, files_found: int, files_per_sec: int) -> None:
        """Called during discovery with count of files found and rate."""
        if self._phase != "discover":
            self._finish_line()
            self._phase = "discover"
        self._write(f"Discovering... {files_found:,} files ({files_per_sec:,}/sec)")

    def on_hash_progress(self, processed: int, total: int, files_per_sec: int) -> None:
        """Called during hashing with processed/total counts and rate."""
        if self._phase != "hash":
            self._finish_line()
            self._phase = "hash"
        self._write(f"Hashing... {processed:,}/{total:,} ({files_per_sec:,}/sec)")

    def on_scan_progress(self, processed: int, total: int, files_per_sec: int) -> None:
        """Called during scanning/introspection with processed/total counts and rate."""
        if self._phase != "scan":
            self._finish_line()
            self._phase = "scan"
        self._write(f"Scanning... {processed:,}/{total:,} ({files_per_sec:,}/sec)")

    def on_language_progress(
        self, processed: int, total: int, current_file: str
    ) -> None:
        """Called during language analysis with progress counts."""
        if self._phase != "language":
            self._finish_line()
            self._phase = "language"
        # Truncate filename if too long
        max_name_len = 40
        if len(current_file) > max_name_len:
            current_file = "..." + current_file[-(max_name_len - 3) :]
        self._write(f"Analyzing languages... {processed:,}/{total:,} [{current_file}]")

    def finish(self) -> None:
        """Finish all progress display."""
        self._finish_line()
        self._phase = ""


def validate_directories(ctx, param, value):
    """Validate that all directories exist."""
    paths = []
    for path_str in value:
        path = Path(path_str)
        if not path.exists():
            raise click.BadParameter(f"Directory not found: {path}")
        if not path.is_dir():
            raise click.BadParameter(f"Not a directory: {path}")
        paths.append(path)
    return paths


def _run_language_analysis(
    conn,
    files,
    progress: ProgressDisplay,
    verbose: bool,
) -> dict:
    """Run language analysis on scanned files with audio tracks.

    Args:
        conn: Database connection.
        files: List of ScannedFile objects.
        progress: Progress display object.
        verbose: Whether to show verbose output.

    Returns:
        Dictionary with 'analyzed', 'skipped', 'errors' counts.
    """
    import logging

    from video_policy_orchestrator.db.models import (
        get_file_by_path,
        get_tracks_for_file,
    )
    from video_policy_orchestrator.language_analysis.service import (
        LanguageAnalysisError,
        analyze_track_languages,
        get_cached_analysis,
        persist_analysis_result,
    )
    from video_policy_orchestrator.plugins.whisper_transcriber.plugin import (
        PluginDependencyError,
        WhisperTranscriptionPlugin,
    )
    from video_policy_orchestrator.transcription.interface import (
        MultiLanguageDetectionConfig,
    )

    logger = logging.getLogger(__name__)
    stats = {"analyzed": 0, "skipped": 0, "errors": 0}

    # Initialize transcriber plugin
    try:
        transcriber = WhisperTranscriptionPlugin()
    except PluginDependencyError as e:
        click.echo(f"\nWarning: {e}", err=True)
        click.echo("Language analysis skipped.", err=True)
        return stats

    # Check if plugin supports multi-language detection
    if not transcriber.supports_feature("multi_language_detection"):
        click.echo(
            "\nWarning: Transcription plugin does not support "
            "multi-language detection.",
            err=True,
        )
        return stats

    # Collect files with audio tracks
    files_to_analyze = []
    for scanned_file in files:
        file_record = get_file_by_path(conn, scanned_file.path)
        if file_record is None or file_record.id is None:
            continue

        tracks = get_tracks_for_file(conn, file_record.id)
        audio_tracks = [t for t in tracks if t.track_type == "audio"]
        if audio_tracks:
            files_to_analyze.append((scanned_file, file_record, audio_tracks))

    if not files_to_analyze:
        return stats

    total = len(files_to_analyze)
    config = MultiLanguageDetectionConfig()

    for i, (scanned_file, file_record, audio_tracks) in enumerate(files_to_analyze):
        progress.on_language_progress(i + 1, total, Path(scanned_file.path).name)

        file_path = Path(scanned_file.path)

        for track in audio_tracks:
            if track.id is None:
                continue

            # Check for cached result
            file_hash = scanned_file.content_hash or ""
            cached = get_cached_analysis(conn, track.id, file_hash)
            if cached is not None:
                stats["skipped"] += 1
                logger.debug(
                    "Using cached language analysis for track %d (%s)",
                    track.id,
                    cached.classification.value,
                )
                continue

            # Get track duration from file metadata
            # We'll use a default if not available
            track_duration = 3600.0  # Default 1 hour

            try:
                result = analyze_track_languages(
                    file_path=file_path,
                    track_index=track.track_index,
                    track_id=track.id,
                    track_duration=track_duration,
                    file_hash=file_hash,
                    transcriber=transcriber,
                    config=config,
                )
                persist_analysis_result(conn, result)
                stats["analyzed"] += 1

                if verbose:
                    click.echo(
                        f"  Track {track.track_index}: "
                        f"{result.classification.value} "
                        f"({result.primary_language} {result.primary_percentage:.0%})"
                    )

            except LanguageAnalysisError as e:
                stats["errors"] += 1
                logger.warning(
                    "Language analysis failed for %s track %d: %s",
                    scanned_file.path,
                    track.track_index,
                    e,
                )
            except Exception as e:
                stats["errors"] += 1
                logger.exception(
                    "Unexpected error analyzing %s track %d: %s",
                    scanned_file.path,
                    track.track_index,
                    e,
                )

        # Commit after each file
        conn.commit()

    return stats


@click.command()
@click.argument(
    "directories",
    nargs=-1,
    required=True,
    callback=validate_directories,
)
@click.option(
    "--extensions",
    "-e",
    default=None,
    help=(
        f"Comma-separated list of file extensions to scan. "
        f"Default: {','.join(DEFAULT_EXTENSIONS)}"
    ),
)
@click.option(
    "--db",
    "db_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Database path. Default: ~/.vpo/library.db",
)
@click.option(
    "--full",
    is_flag=True,
    default=False,
    help="Force full scan, bypass incremental detection.",
)
@click.option(
    "--prune",
    is_flag=True,
    default=False,
    help="Delete database records for missing files.",
)
@click.option(
    "--verify-hash",
    is_flag=True,
    default=False,
    help="Use content hash for change detection (slower).",
)
@click.option(
    "--profile",
    default=None,
    help="Use named configuration profile from ~/.vpo/profiles/.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Scan without writing to database.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Show verbose output.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Output results in JSON format.",
)
@click.option(
    "--analyze-languages",
    is_flag=True,
    default=False,
    help="Analyze audio tracks for multi-language detection.",
)
def scan(
    directories: list[Path],
    extensions: str | None,
    db_path: Path | None,
    full: bool,
    prune: bool,
    verify_hash: bool,
    profile: str | None,
    dry_run: bool,
    verbose: bool,
    json_output: bool,
    analyze_languages: bool,
) -> None:
    """Scan directories for video files.

    Recursively discovers video files in the specified directories,
    computes content hashes, and stores results in the database.

    By default, scans are incremental - only files that have changed since
    the last scan are introspected. Use --full to force a complete rescan.

    Examples:

        vpo scan /media/videos

        vpo scan --extensions mkv,mp4 /media/movies /media/tv

        vpo scan --dry-run --verbose /media/videos

        vpo scan --profile movies /media/movies

        vpo scan --analyze-languages /media/videos
    """
    from video_policy_orchestrator.db.connection import (
        DatabaseLockedError,
        get_connection,
        get_default_db_path,
    )
    from video_policy_orchestrator.db.schema import initialize_database

    # Load profile if specified
    if profile:
        from video_policy_orchestrator.config.profiles import (
            ProfileError,
            list_profiles,
            load_profile,
        )

        try:
            loaded_profile = load_profile(profile)
            if verbose and not json_output:
                click.echo(f"Using profile: {loaded_profile.name}")
        except ProfileError as e:
            available = list_profiles()
            click.echo(f"Error: {e}", err=True)
            if available:
                click.echo("\nAvailable profiles:", err=True)
                for name in sorted(available):
                    click.echo(f"  - {name}", err=True)
            sys.exit(1)

    # Parse extensions
    ext_list = None
    if extensions:
        ext_list = [e.strip().lower().lstrip(".") for e in extensions.split(",")]

    # Create scanner
    scanner = ScannerOrchestrator(extensions=ext_list)

    # Progress callback for verbose mode (legacy)
    def progress_callback(processed: int, total: int) -> None:
        if verbose and not json_output:
            click.echo(f"  Progress: {processed}/{total} files processed...")

    # Create progress display (only if not JSON and TTY)
    progress = ProgressDisplay(enabled=not json_output)

    # Initialize language stats (will be populated if --analyze-languages)
    language_stats = {"analyzed": 0, "skipped": 0, "errors": 0}

    # Run scan
    try:
        if dry_run:
            # Dry run: just scan without database
            files, result = scanner.scan_directories(
                directories, scan_progress=progress
            )
        else:
            # Normal run: scan and persist to database
            from video_policy_orchestrator.jobs.tracking import (
                cancel_scan_job,
                complete_scan_job,
                create_scan_job,
                fail_scan_job,
            )

            effective_db_path = db_path or get_default_db_path()
            with get_connection(effective_db_path) as conn:
                initialize_database(conn)

                # Create job record
                if len(directories) == 1:
                    directory_str = str(directories[0])
                else:
                    directory_str = ",".join(str(d) for d in directories)
                job = create_scan_job(
                    conn,
                    directory_str,
                    incremental=not full,
                    prune=prune,
                    verify_hash=verify_hash,
                )

                try:
                    files, result = scanner.scan_and_persist(
                        directories,
                        conn,
                        progress_callback=progress_callback,
                        full=full,
                        prune=prune,
                        verify_hash=verify_hash,
                        scan_progress=progress,
                        job_id=job.id,
                    )

                    # Run language analysis if requested
                    language_stats = {"analyzed": 0, "skipped": 0, "errors": 0}
                    if analyze_languages and not result.interrupted:
                        language_stats = _run_language_analysis(
                            conn,
                            files,
                            progress,
                            verbose and not json_output,
                        )

                    # job_id is already set in result by scan_and_persist
                    summary = {
                        "total_discovered": result.files_found,
                        "scanned": result.files_new + result.files_updated,
                        "skipped": result.files_skipped,
                        "added": result.files_new,
                        "removed": result.files_removed,
                        "errors": result.files_errored,
                    }
                    if analyze_languages:
                        summary["language_analyzed"] = language_stats["analyzed"]
                        summary["language_skipped"] = language_stats["skipped"]
                        summary["language_errors"] = language_stats["errors"]
                    error_msg = None
                    if result.interrupted:
                        error_msg = "Scan interrupted by user"
                    complete_scan_job(conn, job.id, summary, error_message=error_msg)

                except KeyboardInterrupt:
                    # User pressed Ctrl+C - mark job as cancelled
                    cancel_scan_job(conn, job.id, "Scan aborted by user (Ctrl+C)")
                    progress.finish()
                    click.echo("\nScan aborted by user.", err=True)
                    sys.exit(130)  # Standard exit code for Ctrl+C

                except Exception as e:
                    # Unexpected error - mark job as failed
                    fail_scan_job(conn, job.id, f"Scan failed: {e}")
                    raise  # Re-raise to be handled by outer exception handler

    except DatabaseLockedError as e:
        progress.finish()
        click.echo(f"Error: {e}", err=True)
        click.echo(
            "Hint: Close other VPO instances or use a different --db path.", err=True
        )
        sys.exit(1)

    except Exception as e:
        progress.finish()
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Finish progress display before outputting results
    progress.finish()

    # Output results
    if json_output:
        output_json(result, files, verbose, dry_run, language_stats)
    else:
        output_human(result, files, verbose, dry_run, language_stats)

    # Exit with appropriate code
    if getattr(result, "interrupted", False):
        click.echo("\nScan interrupted. Partial results saved.", err=True)
        sys.exit(130)  # Standard exit code for Ctrl+C
    elif result.errors:
        # Exit 1 only if errors occurred AND no files were found (complete
        # failure). Exit 0 if some files were processed despite errors
        # (partial success).
        sys.exit(1) if not files else sys.exit(0)


def output_json(
    result,
    files,
    verbose: bool,
    dry_run: bool = False,
    language_stats: dict | None = None,
) -> None:
    """Output scan results in JSON format."""
    data = {
        "files_found": result.files_found,
        "elapsed_seconds": round(result.elapsed_seconds, 2),
        "directories_scanned": result.directories_scanned,
        "dry_run": dry_run,
    }

    if not dry_run:
        data["files_new"] = result.files_new
        data["files_updated"] = result.files_updated
        data["files_skipped"] = result.files_skipped
        data["files_removed"] = getattr(result, "files_removed", 0)
        data["incremental"] = getattr(result, "incremental", True)
        if hasattr(result, "job_id") and result.job_id:
            data["job_id"] = result.job_id

    if result.errors:
        data["errors"] = [{"path": p, "error": e} for p, e in result.errors]

    # Add language analysis stats if any tracks were analyzed
    if language_stats and (
        language_stats["analyzed"] > 0
        or language_stats["skipped"] > 0
        or language_stats["errors"] > 0
    ):
        data["language_analysis"] = {
            "analyzed": language_stats["analyzed"],
            "skipped": language_stats["skipped"],
            "errors": language_stats["errors"],
        }

    if verbose:
        data["files"] = [
            {
                "path": f.path,
                "size": f.size,
                "modified_at": f.modified_at.isoformat(),
                "content_hash": f.content_hash,
            }
            for f in files
        ]

    click.echo(json.dumps(data, indent=2))


def output_human(
    result,
    files,
    verbose: bool,
    dry_run: bool = False,
    language_stats: dict | None = None,
) -> None:
    """Output scan results in human-readable format."""
    dir_count = len(result.directories_scanned)
    dir_word = "directory" if dir_count == 1 else "directories"

    # Build header
    if dir_count == 1:
        scan_target = result.directories_scanned[0]
    else:
        scan_target = f"{dir_count} {dir_word}"

    click.echo(f"\nScanning {scan_target}...")
    click.echo(f"  Discovered: {result.files_found:,} files")

    if not dry_run:
        click.echo(f"  Skipped (unchanged): {result.files_skipped:,}")
        click.echo(f"  Scanned (changed): {result.files_new + result.files_updated:,}")
        click.echo(f"  Added (new): {result.files_new:,}")
        if result.files_errored > 0:
            click.echo(f"  Scanned (error): {result.files_errored:,}")
        files_removed = getattr(result, "files_removed", 0)
        if files_removed > 0:
            click.echo(f"  Removed (missing): {files_removed:,}")
    else:
        click.echo("  (dry run - no database changes)")

    # Show language analysis stats if any tracks were analyzed
    if language_stats and (
        language_stats["analyzed"] > 0
        or language_stats["skipped"] > 0
        or language_stats["errors"] > 0
    ):
        click.echo("\nLanguage analysis:")
        click.echo(f"  Analyzed: {language_stats['analyzed']:,} tracks")
        if language_stats["skipped"] > 0:
            click.echo(f"  Skipped (cached): {language_stats['skipped']:,} tracks")
        if language_stats["errors"] > 0:
            click.echo(f"  Errors: {language_stats['errors']:,} tracks")

    # Show job ID if available
    job_id = getattr(result, "job_id", None)
    if job_id:
        job_short = job_id[:8]
        elapsed = result.elapsed_seconds
        click.echo(f"\nScan complete in {elapsed:.1f}s (job: {job_short})")
    else:
        click.echo(f"\nScan complete in {result.elapsed_seconds:.1f}s")

    if verbose and files:
        click.echo("\nFiles found:")
        for f in files:
            size_mb = f.size / (1024 * 1024)
            click.echo(f"  {f.path} ({size_mb:.2f} MB)")

    if result.errors:
        error_count = len(result.errors)
        click.echo(f"\n{error_count} error(s):", err=True)
        if verbose:
            # In verbose mode, show all errors
            for path, error in result.errors:
                click.echo(f"  {path}: {error}", err=True)
        else:
            # In non-verbose mode, show first 5 errors with hint
            for path, error in result.errors[:5]:
                click.echo(f"  {path}: {error}", err=True)
            if error_count > 5:
                click.echo(
                    f"  ... and {error_count - 5} more (use --verbose to see all)",
                    err=True,
                )


# Register with the CLI group
from video_policy_orchestrator.cli import main  # noqa: E402

main.add_command(scan)
