"""Scan command for VPO CLI."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from vpo.plugin import PluginRegistry

from vpo.cli.exit_codes import ExitCode
from vpo.cli.output import warning_output
from vpo.cli.profile_loader import load_profile_or_exit
from vpo.core import truncate_filename
from vpo.language_analysis.orchestrator import (
    LanguageAnalysisOrchestrator,
)
from vpo.plugin import get_default_registry
from vpo.scanner.orchestrator import (
    DEFAULT_EXTENSIONS,
    ScannerOrchestrator,
)

logger = logging.getLogger(__name__)


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
        self._has_output = False

    def _write(self, text: str) -> None:
        """Write text to stdout, clearing previous line."""
        if not self._enabled:
            return
        # \r moves to start of line, \033[K clears to end of line
        sys.stdout.write(f"\r\033[K{text}")
        sys.stdout.flush()
        self._has_output = True

    def _finish_line(self) -> None:
        """Finish current line with newline."""
        if self._enabled and self._has_output:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._has_output = False

    def on_discover_progress(self, files_found: int, files_per_sec: float) -> None:
        """Called during discovery with count of files found and rate."""
        if self._phase != "discover":
            self._finish_line()
            self._phase = "discover"
        rate = _format_rate(files_per_sec)
        self._write(f"Discovering... {files_found:,} files ({rate})")

    def on_hash_progress(
        self, processed: int, total: int, files_per_sec: float
    ) -> None:
        """Called during hashing with processed/total counts and rate."""
        if self._phase != "hash":
            self._finish_line()
            self._phase = "hash"
        rate = _format_rate(files_per_sec)
        self._write(f"Hashing... {processed:,}/{total:,} ({rate})")

    def on_scan_progress(
        self, processed: int, total: int, files_per_sec: float
    ) -> None:
        """Called during scanning/introspection."""
        if self._phase != "scan":
            self._finish_line()
            self._phase = "scan"
        rate = _format_rate(files_per_sec)
        self._write(f"Scanning... {processed:,}/{total:,} ({rate})")

    def on_language_progress(
        self, processed: int, total: int, current_file: str, files_per_sec: float
    ) -> None:
        """Called during language analysis with progress counts and rate."""
        if self._phase != "language":
            self._finish_line()
            self._phase = "language"
        current_file = truncate_filename(current_file, 40)
        self._write(
            f"Analyzing languages... {processed:,}/{total:,} "
            f"({_format_rate(files_per_sec)}) [{current_file}]"
        )

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


def _compute_rate(completed: int, start_time: float) -> float:
    """Compute files-per-second rate from count and monotonic start time."""
    elapsed = time.monotonic() - start_time
    if elapsed <= 0:
        return 0.0
    return completed / elapsed


def _format_rate(rate: float) -> str:
    """Format a files-per-second rate for display.

    Rates >= 1 are shown as comma-separated integers (e.g. '7,440/sec').
    Rates < 1 are shown with one decimal place (e.g. '0.3/sec').
    """
    if rate >= 1.0:
        return f"{int(rate):,}/sec"
    return f"{rate:.1f}/sec"


def _resolve_language_workers(requested: int | None, config_default: int) -> int:
    """Resolve effective worker count for language analysis.

    Uses the CLI ``--workers`` value if provided, otherwise the
    ``processing.workers`` config value. Result is capped at half the
    available CPU cores (minimum 1).

    Args:
        requested: Worker count from CLI (None if not specified).
        config_default: Default from ``processing.workers`` config.

    Returns:
        Effective worker count.
    """
    cpu_count = os.cpu_count() or 2
    max_workers = max(1, cpu_count // 2)
    effective = max(1, requested if requested is not None else config_default)

    if effective <= max_workers:
        return effective

    logger.info(
        "Requested %d workers, capped to %d (half of %d CPUs)",
        effective,
        max_workers,
        cpu_count,
    )
    return max_workers


def _analyze_file_language(
    scanned_file,
    db_path: Path,
    registry: PluginRegistry,
) -> dict:
    """Analyze language for a single file. Thread-safe worker function.

    Each invocation opens its own DB connection and orchestrator instance,
    so this function can safely run in a ``ThreadPoolExecutor``.

    Args:
        scanned_file: ScannedFile object with ``path`` attribute.
        db_path: Path to the database file.
        registry: PluginRegistry (read-only during parallel processing).

    Returns:
        Dict with ``analyzed``, ``skipped``, ``errors``,
        and ``transcriber_available`` counts.
    """
    from vpo.db import get_file_by_path, get_tracks_for_file
    from vpo.db.connection import get_connection

    _empty = {"analyzed": 0, "skipped": 0, "errors": 0, "transcriber_available": True}

    with get_connection(db_path) as worker_conn:
        file_record = get_file_by_path(worker_conn, scanned_file.path)
        if file_record is None or file_record.id is None:
            return _empty

        track_records = get_tracks_for_file(worker_conn, file_record.id)
        orchestrator = LanguageAnalysisOrchestrator(plugin_registry=registry)
        result = orchestrator.analyze_tracks_for_file(
            conn=worker_conn,
            file_record=file_record,
            track_records=track_records,
            file_path=Path(scanned_file.path),
        )

        if result.analyzed > 0:
            worker_conn.commit()

    return {
        "analyzed": result.analyzed,
        "skipped": result.skipped + result.cached,
        "errors": result.errors,
        "transcriber_available": result.transcriber_available,
    }


def _run_language_analysis(
    files,
    progress: ProgressDisplay,
    verbose: bool,
    json_output: bool,
    *,
    db_path: Path,
    workers: int = 1,
) -> dict:
    """Run language analysis on scanned files with audio tracks.

    Args:
        files: List of ScannedFile objects.
        progress: Progress display object.
        verbose: Whether to show verbose output.
        json_output: Whether output is in JSON mode.
        db_path: Path to the database file.
        workers: Number of parallel workers (1 = sequential).

    Returns:
        Dictionary with 'analyzed', 'skipped', 'errors' counts.
    """
    stats = {"analyzed": 0, "skipped": 0, "errors": 0}
    # Registry is initialized once and shared read-only across workers.
    # Do not call mutating methods (register/enable/disable) after this point.
    registry = get_default_registry()
    total_files = len(files)
    start_time = time.monotonic()

    if workers <= 1:
        return _run_language_analysis_sequential(
            files,
            progress,
            verbose,
            json_output,
            db_path=db_path,
            registry=registry,
            total_files=total_files,
            start_time=start_time,
        )

    # Parallel processing with ThreadPoolExecutor
    from concurrent.futures import ThreadPoolExecutor, as_completed

    files_completed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}
        for scanned_file in files:
            future = executor.submit(
                _analyze_file_language, scanned_file, db_path, registry
            )
            futures[future] = scanned_file

        for future in as_completed(futures):
            scanned_file = futures[future]
            files_completed += 1
            progress.on_language_progress(
                files_completed,
                total_files,
                Path(scanned_file.path).name,
                _compute_rate(files_completed, start_time),
            )

            try:
                file_result = future.result()
            except Exception:
                logger.exception(
                    "Language analysis failed for %s",
                    scanned_file.path,
                )
                stats["errors"] += 1
                continue

            if not file_result["transcriber_available"]:
                # Best-effort cancellation: only pending futures are cancelled.
                # Already-running workers will complete; the executor context
                # manager waits for them on exit.
                for f in futures:
                    f.cancel()
                warning_output(
                    "Transcription plugin unavailable or lacks multi-language "
                    "support. Language analysis skipped.",
                    json_output=json_output,
                )
                return stats

            stats["analyzed"] += file_result["analyzed"]
            stats["skipped"] += file_result["skipped"]
            stats["errors"] += file_result["errors"]

    return stats


def _run_language_analysis_sequential(
    files,
    progress: ProgressDisplay,
    verbose: bool,
    json_output: bool,
    *,
    db_path: Path,
    registry: PluginRegistry,
    total_files: int,
    start_time: float,
) -> dict:
    """Sequential language analysis with verbose per-track output.

    Separated from the parallel path to keep verbose per-track callbacks
    (which are not thread-safe) available in single-worker mode.
    """
    from vpo.db import (
        get_file_by_path,
        get_tracks_for_file,
    )
    from vpo.db.connection import get_connection
    from vpo.language_analysis.orchestrator import AnalysisProgress

    stats = {"analyzed": 0, "skipped": 0, "errors": 0}
    files_processed = 0

    with get_connection(db_path) as conn:
        orchestrator = LanguageAnalysisOrchestrator(plugin_registry=registry)

        for scanned_file in files:
            file_record = get_file_by_path(conn, scanned_file.path)
            if file_record is None or file_record.id is None:
                continue

            track_records = get_tracks_for_file(conn, file_record.id)
            file_path = Path(scanned_file.path)

            progress.on_language_progress(
                files_processed + 1,
                total_files,
                file_path.name,
                _compute_rate(files_processed, start_time),
            )

            # Progress callback for verbose output
            def on_track_progress(p: AnalysisProgress) -> None:
                if not verbose or json_output:
                    return
                if p.status == "cached" and p.result:
                    click.echo(
                        f"  Track {p.track_index}: "
                        f"{p.result.classification.value} (cached)"
                    )
                elif p.status == "analyzed" and p.result:
                    click.echo(
                        f"  Track {p.track_index}: "
                        f"{p.result.classification.value} "
                        f"({p.result.primary_language} "
                        f"{p.result.primary_percentage:.0%})"
                    )

            result = orchestrator.analyze_tracks_for_file(
                conn=conn,
                file_record=file_record,
                track_records=track_records,
                file_path=file_path,
                progress_callback=on_track_progress if verbose else None,
            )

            if not result.transcriber_available:
                warning_output(
                    "Transcription plugin unavailable or lacks multi-language "
                    "support. Language analysis skipped.",
                    json_output=json_output,
                )
                return stats

            stats["analyzed"] += result.analyzed
            stats["skipped"] += result.skipped + result.cached
            stats["errors"] += result.errors
            files_processed += 1

            # Checkpoint every 100 files so progress survives interruption
            if files_processed % 100 == 0:
                conn.commit()

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
    hidden=True,
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
    "--workers",
    type=click.IntRange(min=1),
    default=None,
    help="Number of parallel workers for language analysis. Default: from config.",
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
    workers: int | None,
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
    if prune:
        click.echo(
            "Warning: --prune is deprecated. Use 'vpo db prune' instead.",
            err=True,
        )

    from vpo.db.connection import (
        DatabaseLockedError,
        get_connection,
        get_default_db_path,
    )
    from vpo.db.schema import initialize_database

    # Load profile if specified
    if profile:
        loaded_profile = load_profile_or_exit(profile, json_output=json_output)
        if verbose and not json_output:
            click.echo(f"Using profile: {loaded_profile.name}")

    # Parse extensions
    ext_list = None
    if extensions:
        ext_list = [e.strip().casefold().lstrip(".") for e in extensions.split(",")]

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
            from vpo.jobs.tracking import (
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

                    if analyze_languages and not result.interrupted:
                        from vpo.config import get_config

                        config = get_config()
                        effective_workers = _resolve_language_workers(
                            workers, config.processing.workers
                        )
                        language_stats = _run_language_analysis(
                            files,
                            progress,
                            verbose,
                            json_output,
                            db_path=effective_db_path,
                            workers=effective_workers,
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
                    sys.exit(ExitCode.INTERRUPTED)

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
        sys.exit(ExitCode.DATABASE_ERROR)

    except Exception as e:
        progress.finish()
        click.echo(f"Error: {e}", err=True)
        sys.exit(ExitCode.GENERAL_ERROR)

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
        sys.exit(ExitCode.INTERRUPTED)
    elif result.errors:
        # Exit with error only if errors occurred AND no files were found
        # (complete failure). Exit success if some files were processed
        # despite errors (partial success).
        if not files:
            sys.exit(ExitCode.GENERAL_ERROR)
        else:
            sys.exit(ExitCode.SUCCESS)


def _has_language_stats(language_stats: dict | None) -> bool:
    """Return True if language_stats contains any non-zero counts."""
    return bool(
        language_stats
        and (
            language_stats["analyzed"]
            or language_stats["skipped"]
            or language_stats["errors"]
        )
    )


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

    if _has_language_stats(language_stats):
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

    if _has_language_stats(language_stats):
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
from vpo.cli import main  # noqa: E402

main.add_command(scan)
