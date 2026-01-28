"""Scanner module for Video Policy Orchestrator.

This module provides functionality for scanning directories for video files,
computing content hashes, and persisting results to the database.

Public API:
    - ScannerOrchestrator: Main class for scanning directories
    - ScanResult: Result of a scan operation
    - ScannedFile: Represents a discovered file
    - ScanProgressCallback: Protocol for progress callbacks
    - DEFAULT_EXTENSIONS: Default video file extensions to scan
    - file_needs_rescan: Check if a file needs to be rescanned
    - detect_missing_files: Detect files in DB that no longer exist
"""

from vpo.scanner.orchestrator import (
    DEFAULT_EXTENSIONS,
    ScannedFile,
    ScannerOrchestrator,
    ScanProgressCallback,
    ScanResult,
    detect_missing_files,
    file_needs_rescan,
)

__all__ = [
    "DEFAULT_EXTENSIONS",
    "ScannerOrchestrator",
    "ScanProgressCallback",
    "ScanResult",
    "ScannedFile",
    "detect_missing_files",
    "file_needs_rescan",
]
