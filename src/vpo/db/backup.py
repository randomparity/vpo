"""Backup and restore functionality for the VPO library database.

This module provides functions for creating, validating, and restoring
backups of the VPO SQLite database. Backups are stored as compressed
tar.gz archives containing the database and metadata JSON.

Archive format:
    vpo-library-{ISO8601_timestamp}.tar.gz
    ├── library.db              # SQLite database (complete copy)
    └── backup_metadata.json    # BackupMetadata serialized as JSON

Usage:
    from vpo.db.backup import create_backup, restore_backup, list_backups

    # Create a backup
    result = create_backup(db_path, output_path, conn)

    # Restore from backup
    result = restore_backup(backup_path, db_path, force=True)

    # List available backups
    backups = list_backups(backup_dir)
"""

from dataclasses import dataclass
from pathlib import Path

# =============================================================================
# Exceptions
# =============================================================================


class BackupError(Exception):
    """Base class for backup/restore errors."""

    pass


class BackupIOError(BackupError):
    """IO error during backup/restore (disk full, permissions, etc.)."""

    pass


class BackupValidationError(BackupError):
    """Invalid or corrupted backup archive."""

    pass


class BackupSchemaError(BackupError):
    """Schema version incompatibility (backup newer than VPO)."""

    pass


class BackupLockError(BackupError):
    """Database is locked by another process."""

    pass


class InsufficientSpaceError(BackupError):
    """Not enough disk space for operation."""

    pass


# =============================================================================
# Data Types
# =============================================================================


@dataclass(frozen=True)
class BackupMetadata:
    """Metadata describing a backup archive.

    This metadata is stored as backup_metadata.json within the archive
    and provides information needed to validate and restore backups.
    """

    vpo_version: str
    """VPO version that created the backup (e.g., "0.1.0")."""

    schema_version: int
    """Database schema version at backup time."""

    created_at: str
    """UTC timestamp when backup was created (ISO-8601)."""

    database_size_bytes: int
    """Size of the uncompressed database file."""

    file_count: int
    """Number of files in the library at backup time."""

    total_library_size_bytes: int
    """Sum of all media file sizes in the library."""

    compression: str = "gzip"
    """Compression algorithm used (always "gzip" for now)."""


@dataclass(frozen=True)
class BackupInfo:
    """Information about a backup file for listing.

    Contains both filesystem information and extracted metadata
    for display in backup listings.
    """

    path: Path
    """Full path to the backup archive."""

    filename: str
    """Backup filename."""

    created_at: str
    """UTC timestamp from filename or metadata."""

    archive_size_bytes: int
    """Size of the compressed archive file."""

    metadata: BackupMetadata | None
    """Full metadata if archive is readable, else None."""


@dataclass(frozen=True)
class BackupResult:
    """Result of a backup operation.

    Returned by create_backup() with details about the
    created archive.
    """

    success: bool
    """Whether the backup completed successfully."""

    path: Path
    """Path to the created backup file."""

    archive_size_bytes: int
    """Size of the compressed archive."""

    duration_seconds: float
    """Time taken to create the backup."""

    metadata: BackupMetadata
    """Metadata stored in the backup."""


@dataclass(frozen=True)
class RestoreResult:
    """Result of a restore operation.

    Returned by restore_backup() with details about the
    restored database.
    """

    success: bool
    """Whether the restore completed successfully."""

    source_path: Path
    """Path to the backup that was restored."""

    database_path: Path
    """Path where database was restored."""

    duration_seconds: float
    """Time taken to restore."""

    metadata: BackupMetadata
    """Metadata from the restored backup."""

    schema_mismatch: bool
    """True if backup schema differs from current VPO schema."""
