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

import json
import shutil
import sqlite3
import tarfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
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


# =============================================================================
# Constants
# =============================================================================

#: Default backup directory under VPO config
DEFAULT_BACKUP_DIRNAME = "backups"

#: Prefix for backup filenames
BACKUP_FILENAME_PREFIX = "vpo-library-"

#: Extension for backup archives
BACKUP_EXTENSION = ".tar.gz"

#: Name of the database file inside the archive
ARCHIVE_DB_NAME = "library.db"

#: Name of the metadata file inside the archive
ARCHIVE_METADATA_NAME = "backup_metadata.json"

#: Minimum free space multiplier (2x estimated archive size)
SPACE_MULTIPLIER = 2.0

#: Estimated compression ratio for gzip (conservative estimate)
ESTIMATED_COMPRESSION_RATIO = 0.5


# =============================================================================
# Helper Functions
# =============================================================================


def _get_default_backup_dir() -> Path:
    """Get the default backup directory path.

    Returns:
        Path to ~/.vpo/backups/
    """
    return Path.home() / ".vpo" / DEFAULT_BACKUP_DIRNAME


def _generate_backup_filename() -> str:
    """Generate a unique backup filename using UTC timestamp.

    Format: vpo-library-{ISO8601_timestamp}.tar.gz

    Returns:
        Filename string like "vpo-library-2026-02-05T143022Z.tar.gz"
    """
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    return f"{BACKUP_FILENAME_PREFIX}{timestamp}{BACKUP_EXTENSION}"


def _check_disk_space(
    target_dir: Path,
    required_bytes: int,
) -> None:
    """Check if there is sufficient disk space for an operation.

    Args:
        target_dir: Directory where files will be written
        required_bytes: Minimum required free space in bytes

    Raises:
        InsufficientSpaceError: If there isn't enough disk space
    """
    try:
        usage = shutil.disk_usage(target_dir)
        if usage.free < required_bytes:
            raise InsufficientSpaceError(
                f"Insufficient disk space. Need {required_bytes:,} bytes, "
                f"have {usage.free:,} bytes free."
            )
    except OSError as e:
        raise BackupIOError(f"Failed to check disk space: {e}") from e


def _check_database_lock(db_path: Path) -> None:
    """Check if the database is locked by another process.

    Checks for WAL mode lock files and attempts to acquire an exclusive
    lock to verify no active writers.

    Args:
        db_path: Path to the database file

    Raises:
        BackupLockError: If the database is locked
        BackupIOError: If the database cannot be accessed
    """
    # Check for WAL mode lock files
    wal_path = Path(f"{db_path}-wal")

    # WAL file with content indicates possible active connection
    if wal_path.exists() and wal_path.stat().st_size > 0:
        # Try to acquire exclusive lock to verify
        try:
            conn = sqlite3.connect(db_path, timeout=1.0)
            try:
                # Try to get exclusive lock
                conn.execute("BEGIN EXCLUSIVE")
                conn.rollback()
            except sqlite3.OperationalError:
                raise BackupLockError(
                    "Database is locked by another process. "
                    "Stop the VPO daemon or close other VPO instances."
                )
            finally:
                conn.close()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                raise BackupLockError(
                    "Database is locked by another process. "
                    "Stop the VPO daemon or close other VPO instances."
                )
            raise BackupIOError(f"Failed to access database: {e}") from e

    # Clean check - no WAL files, but verify database is accessible
    if not db_path.exists():
        raise BackupIOError(f"Database not found: {db_path}")


def _get_library_stats(conn: sqlite3.Connection) -> tuple[int, int]:
    """Query file count and total library size from database.

    Args:
        conn: Database connection

    Returns:
        Tuple of (file_count, total_size_bytes)
    """
    cursor = conn.execute("SELECT COUNT(*), COALESCE(SUM(size_bytes), 0) FROM files")
    row = cursor.fetchone()
    return (row[0], row[1])


def _read_backup_metadata(archive_path: Path) -> BackupMetadata:
    """Extract and parse metadata JSON from a backup archive.

    Args:
        archive_path: Path to the backup archive

    Returns:
        Parsed BackupMetadata

    Raises:
        BackupValidationError: If archive is invalid or metadata is missing/corrupt
    """
    try:
        with tarfile.open(archive_path, "r:gz") as tf:
            # Check for metadata file
            try:
                member = tf.getmember(ARCHIVE_METADATA_NAME)
            except KeyError:
                raise BackupValidationError(
                    f"Invalid backup archive: missing {ARCHIVE_METADATA_NAME}"
                )

            # Extract and parse
            f = tf.extractfile(member)
            if f is None:
                raise BackupValidationError(
                    f"Failed to read {ARCHIVE_METADATA_NAME} from archive"
                )

            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise BackupValidationError(f"Invalid metadata JSON: {e}") from e

            # Validate required fields
            required_fields = [
                "vpo_version",
                "schema_version",
                "created_at",
                "database_size_bytes",
                "file_count",
                "total_library_size_bytes",
            ]
            missing = [f for f in required_fields if f not in data]
            if missing:
                raise BackupValidationError(
                    f"Metadata missing required fields: {missing}"
                )

            return BackupMetadata(
                vpo_version=data["vpo_version"],
                schema_version=data["schema_version"],
                created_at=data["created_at"],
                database_size_bytes=data["database_size_bytes"],
                file_count=data["file_count"],
                total_library_size_bytes=data["total_library_size_bytes"],
                compression=data.get("compression", "gzip"),
            )
    except tarfile.TarError as e:
        raise BackupValidationError(f"Invalid tar archive: {e}") from e
    except OSError as e:
        raise BackupIOError(f"Failed to read archive: {e}") from e


def _serialize_metadata(metadata: BackupMetadata) -> str:
    """Serialize BackupMetadata to JSON string.

    Args:
        metadata: Metadata to serialize

    Returns:
        JSON string
    """
    return json.dumps(asdict(metadata), indent=2)
