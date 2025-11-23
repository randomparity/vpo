"""Scanner orchestrator that coordinates Rust core with database operations."""

from __future__ import annotations

import signal
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from video_policy_orchestrator._core import discover_videos, hash_files
from video_policy_orchestrator.db.models import FileRecord

if TYPE_CHECKING:
    from video_policy_orchestrator.introspector.interface import MediaIntrospector


class ScanProgressCallback(Protocol):
    """Protocol for scan progress callbacks."""

    def on_discover_progress(self, files_found: int) -> None:
        """Called during discovery with count of files found."""
        ...

    def on_hash_progress(self, processed: int, total: int) -> None:
        """Called during hashing with processed/total counts."""
        ...

    def on_scan_progress(self, processed: int, total: int) -> None:
        """Called during scanning/introspection with processed/total counts."""
        ...


@dataclass
class ScanResult:
    """Result of a scan operation."""

    files_found: int = 0
    files_new: int = 0
    files_updated: int = 0
    files_skipped: int = 0
    files_errored: int = 0
    files_removed: int = 0  # Files marked as missing or deleted
    errors: list[tuple[str, str]] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    directories_scanned: list[str] = field(default_factory=list)
    interrupted: bool = False  # True if scan was interrupted by Ctrl+C
    incremental: bool = True  # Whether incremental mode was used
    job_id: str | None = None  # UUID of the scan job (if job tracking enabled)


@dataclass
class ScannedFile:
    """A file discovered during scanning."""

    path: str
    size: int
    modified_at: datetime
    content_hash: str | None = None
    hash_error: str | None = None


DEFAULT_EXTENSIONS = ["mkv", "mp4", "avi", "webm", "m4v", "mov"]


def file_needs_rescan(
    existing_record: FileRecord | None,
    current_mtime: datetime,
    current_size: int,
) -> bool:
    """Determine if a file needs to be rescanned.

    Uses mtime + size comparison for efficient change detection.

    Args:
        existing_record: Existing database record (None if new file).
        current_mtime: Current file modification time (UTC).
        current_size: Current file size in bytes.

    Returns:
        True if file needs rescan, False if unchanged.
    """
    # New file - always needs scan
    if existing_record is None:
        return True

    # Compare mtime (stored as ISO-8601 string)
    stored_mtime = datetime.fromisoformat(existing_record.modified_at)
    if stored_mtime != current_mtime:
        return True

    # Compare size
    if existing_record.size_bytes != current_size:
        return True

    return False


def detect_missing_files(db_paths: list[str]) -> list[str]:
    """Detect files in database that no longer exist on disk.

    Args:
        db_paths: List of file paths from database records.

    Returns:
        List of paths that no longer exist or are not regular files.
    """
    missing = []
    for path_str in db_paths:
        path = Path(path_str)
        if not path.exists() or not path.is_file():
            missing.append(path_str)
    return missing


class ScannerOrchestrator:
    """Coordinates file discovery, hashing, and database operations."""

    def __init__(
        self,
        extensions: list[str] | None = None,
        follow_symlinks: bool = False,
    ):
        """Initialize the scanner.

        Args:
            extensions: List of file extensions to scan for.
            follow_symlinks: Whether to follow symbolic links.
        """
        self.extensions = extensions or DEFAULT_EXTENSIONS
        self.follow_symlinks = follow_symlinks
        self._interrupt_event = threading.Event()

    def _create_signal_handler(self) -> Callable[[int, object], None]:
        """Create a signal handler that sets the interrupt event."""

        def handler(signum: int, frame: object) -> None:
            self._interrupt_event.set()

        return handler

    def _is_interrupted(self) -> bool:
        """Check if the scan has been interrupted."""
        return self._interrupt_event.is_set()

    def scan_directories(
        self,
        directories: list[Path],
        compute_hashes: bool = True,
        progress_callback: Callable[[int, int], None] | None = None,
        scan_progress: ScanProgressCallback | None = None,
    ) -> tuple[list[ScannedFile], ScanResult]:
        """Scan directories for video files.

        Args:
            directories: List of directories to scan.
            compute_hashes: Whether to compute content hashes.
            progress_callback: Optional callback for progress updates (deprecated).
            scan_progress: Optional progress callback object for detailed progress.

        Returns:
            Tuple of (list of scanned files, scan result summary).
        """
        start_time = time.time()
        result = ScanResult()
        result.directories_scanned = [str(d) for d in directories]

        all_files: list[ScannedFile] = []

        # Create progress callback for discovery if progress reporting enabled
        discover_cb = None
        if scan_progress is not None:
            discover_cb = scan_progress.on_discover_progress

        # Discover files in all directories
        for directory in directories:
            try:
                discovered = discover_videos(
                    str(directory),
                    self.extensions,
                    self.follow_symlinks,
                    progress_callback=discover_cb,
                )

                for file_info in discovered:
                    scanned = ScannedFile(
                        path=file_info["path"],
                        size=file_info["size"],
                        modified_at=datetime.fromtimestamp(
                            file_info["modified"], tz=timezone.utc
                        ),
                    )
                    all_files.append(scanned)

            except (FileNotFoundError, NotADirectoryError) as e:
                result.errors.append((str(directory), str(e)))
                result.files_errored += 1

        result.files_found = len(all_files)

        # Create progress callback for hashing if progress reporting enabled
        hash_cb = None
        if scan_progress is not None:
            hash_cb = scan_progress.on_hash_progress

        # Compute hashes if requested
        if compute_hashes and all_files:
            paths = [f.path for f in all_files]
            hash_results = hash_files(paths, progress_callback=hash_cb)

            path_to_file = {f.path: f for f in all_files}
            for hash_result in hash_results:
                file = path_to_file.get(hash_result["path"])
                if file:
                    file.content_hash = hash_result["hash"]
                    file.hash_error = hash_result["error"]
                    if hash_result["error"]:
                        result.errors.append(
                            (hash_result["path"], hash_result["error"])
                        )

        result.elapsed_seconds = time.time() - start_time
        return all_files, result

    def scan_and_persist(
        self,
        directories: list[Path],
        conn: sqlite3.Connection,
        compute_hashes: bool = True,
        progress_callback: Callable[[int, int], None] | None = None,
        introspector: MediaIntrospector | None = None,
        *,
        full: bool = False,
        prune: bool = False,
        verify_hash: bool = False,
        scan_progress: ScanProgressCallback | None = None,
    ) -> tuple[list[ScannedFile], ScanResult]:
        """Scan directories and persist results to database.

        Args:
            directories: List of directories to scan.
            conn: Database connection.
            compute_hashes: Whether to compute content hashes.
            progress_callback: Optional callback(processed, total) for progress.
            introspector: Optional MediaIntrospector for extracting metadata.
            full: If True, force full scan bypassing incremental detection.
            prune: If True, delete database records for missing files.
            verify_hash: If True, use content hash for change detection (slower).
            scan_progress: Optional progress callback object for detailed progress.

        Returns:
            Tuple of (list of scanned files, scan result summary).
        """
        # Reset interrupt event for this scan
        self._interrupt_event.clear()

        from video_policy_orchestrator.db.models import (
            FileRecord,
            delete_file,
            get_file_by_path,
            upsert_file,
            upsert_tracks_for_file,
        )
        from video_policy_orchestrator.introspector.ffprobe import FFprobeIntrospector
        from video_policy_orchestrator.introspector.interface import (
            MediaIntrospectionError,
        )
        from video_policy_orchestrator.introspector.stub import StubIntrospector

        # Set up signal handler for graceful shutdown
        old_handler = signal.signal(signal.SIGINT, self._create_signal_handler())

        try:
            # Use FFprobeIntrospector if available, otherwise fall back to stub
            if introspector is None:
                if FFprobeIntrospector.is_available():
                    introspector = FFprobeIntrospector()
                else:
                    introspector = StubIntrospector()

            start_time = time.time()
            result = ScanResult()
            result.directories_scanned = [str(d) for d in directories]
            result.incremental = not full

            all_files: list[ScannedFile] = []

            # Create progress callback for discovery if progress reporting enabled
            discover_cb = None
            if scan_progress is not None:
                discover_cb = scan_progress.on_discover_progress

            # Discover files in all directories
            for directory in directories:
                if self._is_interrupted():
                    break
                try:
                    discovered = discover_videos(
                        str(directory),
                        self.extensions,
                        self.follow_symlinks,
                        progress_callback=discover_cb,
                    )

                    for file_info in discovered:
                        scanned = ScannedFile(
                            path=file_info["path"],
                            size=file_info["size"],
                            modified_at=datetime.fromtimestamp(
                                file_info["modified"], tz=timezone.utc
                            ),
                        )
                        all_files.append(scanned)

                except (FileNotFoundError, NotADirectoryError) as e:
                    result.errors.append((str(directory), str(e)))
                    result.files_errored += 1

            result.files_found = len(all_files)

            # Check which files need processing (new or modified)
            # Cache existing records to avoid duplicate lookups during persist phase
            files_to_process: list[ScannedFile] = []
            existing_records: dict[str, FileRecord | None] = {}
            discovered_paths = {f.path for f in all_files}

            for scanned in all_files:
                if self._is_interrupted():
                    break
                existing = get_file_by_path(conn, scanned.path)
                existing_records[scanned.path] = existing

                if full:
                    # Full scan: process all files
                    files_to_process.append(scanned)
                elif existing is None:
                    # New file - always process
                    files_to_process.append(scanned)
                else:
                    # Check if file needs rescan using mtime + size
                    needs_rescan = file_needs_rescan(
                        existing_record=existing,
                        current_mtime=scanned.modified_at,
                        current_size=scanned.size,
                    )
                    if needs_rescan:
                        files_to_process.append(scanned)
                    else:
                        result.files_skipped += 1

            # Handle missing files (files in DB but not on disk)
            if not self._is_interrupted():
                # Get all file paths from DB for the scanned directories
                db_paths_in_dirs = []
                for directory in directories:
                    cursor = conn.execute(
                        "SELECT path FROM files WHERE directory LIKE ?",
                        (f"{directory}%",),
                    )
                    db_paths_in_dirs.extend(row[0] for row in cursor.fetchall())

                missing_paths = detect_missing_files(db_paths_in_dirs)
                for missing_path in missing_paths:
                    if missing_path not in discovered_paths:
                        if prune:
                            # Delete record for missing file
                            record = get_file_by_path(conn, missing_path)
                            if record and record.id:
                                delete_file(conn, record.id)
                                result.files_removed += 1
                        else:
                            # Mark file as missing
                            # Note: Commit per-file for immediate visibility during
                            # long-running scans. WAL mode handles concurrent reads.
                            update_sql = (
                                "UPDATE files SET scan_status = 'missing' "
                                "WHERE path = ?"
                            )
                            conn.execute(update_sql, (missing_path,))
                            conn.commit()
                            result.files_removed += 1

            # Create progress callback for hashing if progress reporting enabled
            hash_cb = None
            if scan_progress is not None:
                hash_cb = scan_progress.on_hash_progress

            # Compute hashes only for files that need processing
            if compute_hashes and files_to_process and not self._is_interrupted():
                paths = [f.path for f in files_to_process]
                hash_results = hash_files(paths, progress_callback=hash_cb)

                path_to_file = {f.path: f for f in files_to_process}
                for hash_result in hash_results:
                    file = path_to_file.get(hash_result["path"])
                    if file:
                        file.content_hash = hash_result["hash"]
                        file.hash_error = hash_result["error"]
                        if hash_result["error"]:
                            result.errors.append(
                                (hash_result["path"], hash_result["error"])
                            )

            # verify_hash mode: compute hashes for skipped files and check for changes
            if verify_hash and not full and not self._is_interrupted():
                skipped_files = [
                    f
                    for f in all_files
                    if f.path not in {sf.path for sf in files_to_process}
                ]
                if skipped_files:
                    skipped_paths = [f.path for f in skipped_files]
                    verify_hash_results = hash_files(
                        skipped_paths, progress_callback=hash_cb
                    )

                    # Check if hash changed for any skipped file
                    for hash_result in verify_hash_results:
                        if hash_result["error"]:
                            continue
                        existing = existing_records.get(hash_result["path"])
                        if existing and existing.content_hash != hash_result["hash"]:
                            # Hash changed - need to process this file
                            for f in skipped_files:
                                if f.path == hash_result["path"]:
                                    f.content_hash = hash_result["hash"]
                                    files_to_process.append(f)
                                    result.files_skipped -= 1
                                    break

            # Persist to database with progress reporting
            now = datetime.now(timezone.utc)
            total_to_process = len(files_to_process)
            for i, scanned in enumerate(files_to_process):
                if self._is_interrupted():
                    result.interrupted = True
                    break

                path = Path(scanned.path)
                # Use cached lookup result instead of querying again
                existing = existing_records.get(scanned.path)

                # Get container format and tracks from introspector
                container_format = None
                introspection_result = None
                introspection_error = None
                try:
                    introspection_result = introspector.get_file_info(path)
                    container_format = introspection_result.container_format
                except MediaIntrospectionError as e:
                    # Capture error for database storage
                    introspection_error = str(e)
                    result.files_errored += 1
                except Exception as e:
                    # Catch any other unexpected errors
                    introspection_error = f"Unexpected error: {e}"
                    result.files_errored += 1

                # Determine scan status: hash_error takes precedence
                if scanned.hash_error:
                    scan_status = "error"
                    scan_error = scanned.hash_error
                elif introspection_error:
                    scan_status = "error"
                    scan_error = introspection_error
                else:
                    scan_status = "ok"
                    scan_error = None

                record = FileRecord(
                    id=None,
                    path=scanned.path,
                    filename=path.name,
                    directory=str(path.parent),
                    extension=path.suffix.lstrip(".").lower(),
                    size_bytes=scanned.size,
                    modified_at=scanned.modified_at.isoformat(),
                    content_hash=scanned.content_hash,
                    container_format=container_format,
                    scanned_at=now.isoformat(),
                    scan_status=scan_status,
                    scan_error=scan_error,
                )

                file_id = upsert_file(conn, record)

                # Persist tracks if introspection succeeded
                if introspection_result is not None and introspection_result.tracks:
                    upsert_tracks_for_file(conn, file_id, introspection_result.tracks)

                if existing is None:
                    result.files_new += 1
                else:
                    result.files_updated += 1

                # Report progress
                processed = i + 1
                # Use new scan_progress callback if available
                if scan_progress is not None:
                    scan_progress.on_scan_progress(processed, total_to_process)
                # Fall back to legacy progress_callback (every 100 files)
                elif progress_callback and processed % 100 == 0:
                    progress_callback(processed, total_to_process)

            result.elapsed_seconds = time.time() - start_time
            return all_files, result

        finally:
            # Restore original signal handler
            signal.signal(signal.SIGINT, old_handler)
