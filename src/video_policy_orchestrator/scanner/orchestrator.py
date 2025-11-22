"""Scanner orchestrator that coordinates Rust core with database operations."""

from __future__ import annotations

import signal
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from video_policy_orchestrator._core import discover_videos, hash_files

if TYPE_CHECKING:
    from video_policy_orchestrator.introspector.interface import MediaIntrospector

# Global flag for graceful shutdown
_interrupted = False


def _signal_handler(signum: int, frame) -> None:
    """Handle interrupt signal (Ctrl+C) for graceful shutdown."""
    global _interrupted
    _interrupted = True


@dataclass
class ScanResult:
    """Result of a scan operation."""

    files_found: int = 0
    files_new: int = 0
    files_updated: int = 0
    files_skipped: int = 0
    files_errored: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    directories_scanned: list[str] = field(default_factory=list)
    interrupted: bool = False  # True if scan was interrupted by Ctrl+C


@dataclass
class ScannedFile:
    """A file discovered during scanning."""

    path: str
    size: int
    modified_at: datetime
    content_hash: str | None = None
    hash_error: str | None = None


DEFAULT_EXTENSIONS = ["mkv", "mp4", "avi", "webm", "m4v", "mov"]


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

    def scan_directories(
        self,
        directories: list[Path],
        compute_hashes: bool = True,
        progress_callback: callable = None,
    ) -> tuple[list[ScannedFile], ScanResult]:
        """Scan directories for video files.

        Args:
            directories: List of directories to scan.
            compute_hashes: Whether to compute content hashes.
            progress_callback: Optional callback for progress updates.

        Returns:
            Tuple of (list of scanned files, scan result summary).
        """
        start_time = time.time()
        result = ScanResult()
        result.directories_scanned = [str(d) for d in directories]

        all_files: list[ScannedFile] = []

        # Discover files in all directories
        for directory in directories:
            try:
                discovered = discover_videos(
                    str(directory),
                    self.extensions,
                    self.follow_symlinks,
                )

                for file_info in discovered:
                    scanned = ScannedFile(
                        path=file_info["path"],
                        size=file_info["size"],
                        modified_at=datetime.fromtimestamp(file_info["modified"]),
                    )
                    all_files.append(scanned)

            except (FileNotFoundError, NotADirectoryError) as e:
                result.errors.append((str(directory), str(e)))
                result.files_errored += 1

        result.files_found = len(all_files)

        # Compute hashes if requested
        if compute_hashes and all_files:
            paths = [f.path for f in all_files]
            hash_results = hash_files(paths)

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
    ) -> tuple[list[ScannedFile], ScanResult]:
        """Scan directories and persist results to database.

        Args:
            directories: List of directories to scan.
            conn: Database connection.
            compute_hashes: Whether to compute content hashes.
            progress_callback: Optional callback(processed, total) for progress.
            introspector: Optional MediaIntrospector for extracting metadata.

        Returns:
            Tuple of (list of scanned files, scan result summary).
        """
        global _interrupted
        _interrupted = False

        from video_policy_orchestrator.db.models import (
            FileRecord,
            get_file_by_path,
            upsert_file,
        )
        from video_policy_orchestrator.introspector.stub import StubIntrospector

        # Set up signal handler for graceful shutdown
        old_handler = signal.signal(signal.SIGINT, _signal_handler)

        try:
            # Use stub introspector by default
            if introspector is None:
                introspector = StubIntrospector()

            start_time = time.time()
            result = ScanResult()
            result.directories_scanned = [str(d) for d in directories]

            all_files: list[ScannedFile] = []

            # Discover files in all directories
            for directory in directories:
                if _interrupted:
                    break
                try:
                    discovered = discover_videos(
                        str(directory),
                        self.extensions,
                        self.follow_symlinks,
                    )

                    for file_info in discovered:
                        scanned = ScannedFile(
                            path=file_info["path"],
                            size=file_info["size"],
                            modified_at=datetime.fromtimestamp(file_info["modified"]),
                        )
                        all_files.append(scanned)

                except (FileNotFoundError, NotADirectoryError) as e:
                    result.errors.append((str(directory), str(e)))
                    result.files_errored += 1

            result.files_found = len(all_files)

            # Check which files need processing (new or modified)
            files_to_process: list[ScannedFile] = []
            for scanned in all_files:
                if _interrupted:
                    break
                existing = get_file_by_path(conn, scanned.path)
                if existing is None:
                    # New file
                    files_to_process.append(scanned)
                else:
                    # Check if modified
                    existing_modified = existing.modified_at
                    scanned_modified = scanned.modified_at.isoformat()
                    if existing_modified != scanned_modified:
                        files_to_process.append(scanned)
                    else:
                        result.files_skipped += 1

            # Compute hashes only for files that need processing
            if compute_hashes and files_to_process and not _interrupted:
                paths = [f.path for f in files_to_process]
                hash_results = hash_files(paths)

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

            # Persist to database with progress reporting
            now = datetime.now()
            total_to_process = len(files_to_process)
            for i, scanned in enumerate(files_to_process):
                if _interrupted:
                    result.interrupted = True
                    break

                path = Path(scanned.path)
                existing = get_file_by_path(conn, scanned.path)

                # Get container format from introspector
                container_format = None
                try:
                    file_info = introspector.get_file_info(path)
                    container_format = file_info.container_format
                except Exception:
                    # If introspection fails, continue without container format
                    pass

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
                    scan_status="error" if scanned.hash_error else "ok",
                    scan_error=scanned.hash_error,
                )

                upsert_file(conn, record)

                if existing is None:
                    result.files_new += 1
                else:
                    result.files_updated += 1

                # Report progress every 100 files
                processed = i + 1
                if progress_callback and processed % 100 == 0:
                    progress_callback(processed, total_to_process)

            result.elapsed_seconds = time.time() - start_time
            return all_files, result

        finally:
            # Restore original signal handler
            signal.signal(signal.SIGINT, old_handler)
