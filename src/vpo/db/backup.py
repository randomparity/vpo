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
import logging
import shutil
import sqlite3
import tarfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

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


# =============================================================================
# Public API - Backup Operations
# =============================================================================


def create_backup(
    db_path: Path,
    output_path: Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> BackupResult:
    """Create a backup archive of the database.

    Uses the SQLite online backup API to safely copy the database,
    then creates a compressed tar.gz archive with the database and
    metadata JSON.

    Args:
        db_path: Path to the source database file
        output_path: Optional output path for the backup archive.
            If not provided, creates backup in default directory with
            auto-generated timestamp filename.
        conn: Optional existing connection to use for stats query.
            If not provided, opens a new connection.

    Returns:
        BackupResult with details about the created backup

    Raises:
        BackupLockError: If the database is locked
        InsufficientSpaceError: If there isn't enough disk space
        BackupIOError: If an IO error occurs during backup
    """
    import tempfile
    import time

    from vpo import __version__ as vpo_version
    from vpo.db.schema import SCHEMA_VERSION

    start_time = time.monotonic()

    # Resolve paths
    db_path = Path(db_path).resolve()
    if output_path is None:
        backup_dir = _get_default_backup_dir()
        backup_dir.mkdir(parents=True, exist_ok=True)
        output_path = backup_dir / _generate_backup_filename()
    else:
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Starting backup",
        extra={"db_path": str(db_path), "output": str(output_path)},
    )

    # Check database accessibility and lock status
    _check_database_lock(db_path)

    # Get database size for space check
    try:
        db_size = db_path.stat().st_size
    except OSError as e:
        raise BackupIOError(f"Failed to read database: {e}") from e

    # Check disk space (need space for temp copy + archive)
    estimated_archive_size = int(db_size * ESTIMATED_COMPRESSION_RATIO)
    required_space = int(db_size + estimated_archive_size * SPACE_MULTIPLIER)
    _check_disk_space(output_path.parent, required_space)

    # Get library stats
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(db_path)
        close_conn = True

    try:
        file_count, total_library_size = _get_library_stats(conn)

        # Create temp directory for backup operations
        with tempfile.TemporaryDirectory(prefix="vpo-backup-") as temp_dir:
            temp_path = Path(temp_dir)
            temp_db = temp_path / ARCHIVE_DB_NAME

            # Use SQLite online backup API
            backup_conn = sqlite3.connect(temp_db)
            try:
                conn.backup(backup_conn)
            finally:
                backup_conn.close()

            # Create metadata
            metadata = BackupMetadata(
                vpo_version=vpo_version,
                schema_version=SCHEMA_VERSION,
                created_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                database_size_bytes=db_size,
                file_count=file_count,
                total_library_size_bytes=total_library_size,
                compression="gzip",
            )

            # Write metadata JSON
            metadata_path = temp_path / ARCHIVE_METADATA_NAME
            metadata_path.write_text(_serialize_metadata(metadata))

            # Create tar.gz archive
            temp_archive = temp_path / "archive.tar.gz"
            try:
                with tarfile.open(temp_archive, "w:gz") as tf:
                    tf.add(temp_db, arcname=ARCHIVE_DB_NAME)
                    tf.add(metadata_path, arcname=ARCHIVE_METADATA_NAME)
            except (tarfile.TarError, OSError) as e:
                raise BackupIOError(f"Failed to create archive: {e}") from e

            # Move to final destination
            try:
                shutil.move(str(temp_archive), str(output_path))
            except OSError as e:
                raise BackupIOError(
                    f"Failed to move archive to destination: {e}"
                ) from e

        # Get archive size
        archive_size = output_path.stat().st_size

    finally:
        if close_conn:
            conn.close()

    duration = time.monotonic() - start_time

    logger.info(
        "Backup complete",
        extra={
            "output": str(output_path),
            "archive_size": archive_size,
            "db_size": metadata.database_size_bytes,
            "file_count": metadata.file_count,
            "duration_seconds": round(duration, 2),
        },
    )

    return BackupResult(
        success=True,
        path=output_path,
        archive_size_bytes=archive_size,
        duration_seconds=duration,
        metadata=metadata,
    )


def validate_backup(backup_path: Path) -> BackupMetadata:
    """Validate a backup archive and return its metadata.

    Checks:
    - Archive is a valid tar.gz file
    - Contains required files (library.db, backup_metadata.json)
    - Metadata JSON is valid and complete
    - Database passes SQLite integrity check (quick_check)

    Args:
        backup_path: Path to the backup archive

    Returns:
        BackupMetadata from the archive

    Raises:
        BackupValidationError: If archive is invalid or corrupted
        BackupIOError: If archive cannot be read
    """
    import tempfile

    backup_path = Path(backup_path).resolve()

    # Validate file exists and is readable
    if not backup_path.exists():
        raise BackupIOError(f"Backup file not found: {backup_path}")

    if not backup_path.is_file():
        raise BackupValidationError(f"Not a file: {backup_path}")

    # Check it's a tar.gz file
    if not backup_path.name.endswith(".tar.gz"):
        raise BackupValidationError(
            f"Invalid backup format: expected .tar.gz file, got {backup_path.name}"
        )

    # Try to open as tar.gz
    try:
        with tarfile.open(backup_path, "r:gz") as tf:
            members = tf.getnames()
    except tarfile.TarError as e:
        raise BackupValidationError(f"Invalid tar archive: {e}") from e
    except OSError as e:
        raise BackupIOError(f"Failed to read archive: {e}") from e

    # Check required files
    if ARCHIVE_DB_NAME not in members:
        raise BackupValidationError(
            f"Invalid backup archive: missing {ARCHIVE_DB_NAME}"
        )
    if ARCHIVE_METADATA_NAME not in members:
        raise BackupValidationError(
            f"Invalid backup archive: missing {ARCHIVE_METADATA_NAME}"
        )

    # Read and validate metadata
    metadata = _read_backup_metadata(backup_path)

    # Extract database to temp file and run integrity check
    with tempfile.TemporaryDirectory(prefix="vpo-validate-") as temp_dir:
        temp_path = Path(temp_dir)
        temp_db = temp_path / ARCHIVE_DB_NAME

        try:
            with tarfile.open(backup_path, "r:gz") as tf:
                tf.extract(ARCHIVE_DB_NAME, temp_path)
        except (tarfile.TarError, OSError) as e:
            raise BackupValidationError(
                f"Failed to extract database for validation: {e}"
            ) from e

        # Run SQLite integrity check
        try:
            conn = sqlite3.connect(temp_db)
            cursor = conn.execute("PRAGMA quick_check")
            result = cursor.fetchone()
            conn.close()

            if result[0] != "ok":
                raise BackupValidationError(
                    f"Database integrity check failed: {result[0]}"
                )
        except sqlite3.Error as e:
            raise BackupValidationError(f"Database integrity check failed: {e}") from e

    return metadata


def restore_backup(
    backup_path: Path,
    db_path: Path,
    force: bool = False,
) -> RestoreResult:
    """Restore database from a backup archive.

    Extracts the database from the backup archive and replaces the
    current database atomically (extract to temp, then rename).

    Args:
        backup_path: Path to the backup archive
        db_path: Path where database should be restored
        force: If True, skip schema version check for newer backups

    Returns:
        RestoreResult with details about the restore

    Raises:
        BackupValidationError: If archive is invalid
        BackupSchemaError: If backup schema is newer than current VPO
        BackupLockError: If the database is locked
        InsufficientSpaceError: If there isn't enough disk space
        BackupIOError: If an IO error occurs
    """
    import time

    from vpo.db.schema import SCHEMA_VERSION

    start_time = time.monotonic()

    backup_path = Path(backup_path).resolve()
    db_path = Path(db_path).resolve()

    logger.info(
        "Starting restore",
        extra={"backup": str(backup_path), "target": str(db_path)},
    )

    # Validate backup
    metadata = validate_backup(backup_path)

    # Check schema version
    schema_mismatch = metadata.schema_version != SCHEMA_VERSION
    if metadata.schema_version > SCHEMA_VERSION and not force:
        raise BackupSchemaError(
            f"Backup schema version ({metadata.schema_version}) is newer than "
            f"current VPO schema ({SCHEMA_VERSION}). "
            "Update VPO before restoring this backup."
        )

    # Check if database exists and is locked
    if db_path.exists():
        _check_database_lock(db_path)

    # Check disk space
    _check_disk_space(db_path.parent, metadata.database_size_bytes * 2)

    # Create parent directory if needed
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Extract to temp file in same directory (for atomic rename)
    temp_db = db_path.with_suffix(".db.restore-tmp")
    try:
        with tarfile.open(backup_path, "r:gz") as tf:
            # Extract database to temp file
            member = tf.getmember(ARCHIVE_DB_NAME)
            f = tf.extractfile(member)
            if f is None:
                raise BackupValidationError("Failed to extract database from archive")

            # Write to temp file
            with open(temp_db, "wb") as out:
                shutil.copyfileobj(f, out)

        # Verify extracted database
        try:
            conn = sqlite3.connect(temp_db)
            cursor = conn.execute("PRAGMA quick_check")
            result = cursor.fetchone()
            conn.close()

            if result[0] != "ok":
                raise BackupValidationError(
                    f"Restored database integrity check failed: {result[0]}"
                )
        except sqlite3.Error as e:
            raise BackupValidationError(
                f"Restored database integrity check failed: {e}"
            ) from e

        # Atomic rename to final destination
        # Remove WAL and SHM files if they exist
        for ext in ["-wal", "-shm"]:
            wal_file = Path(f"{db_path}{ext}")
            if wal_file.exists():
                wal_file.unlink()

        # Replace database
        temp_db.replace(db_path)

    except Exception:
        # Clean up temp file on error
        if temp_db.exists():
            temp_db.unlink()
        raise

    duration = time.monotonic() - start_time

    logger.info(
        "Restore complete",
        extra={
            "backup": str(backup_path),
            "target": str(db_path),
            "file_count": metadata.file_count,
            "schema_mismatch": schema_mismatch,
            "duration_seconds": round(duration, 2),
        },
    )

    return RestoreResult(
        success=True,
        source_path=backup_path,
        database_path=db_path,
        duration_seconds=duration,
        metadata=metadata,
        schema_mismatch=schema_mismatch,
    )


def list_backups(backup_dir: Path | None = None) -> list[BackupInfo]:
    """List available backups in a directory.

    Scans for vpo-library-*.tar.gz files and extracts metadata from
    each valid archive. Returns results sorted by creation date
    (newest first).

    Args:
        backup_dir: Directory to scan. If None, uses default backup
            directory (~/.vpo/backups/).

    Returns:
        List of BackupInfo for each found backup, sorted newest first.
        Backups with unreadable metadata will have metadata=None.

    Raises:
        BackupIOError: If directory cannot be read
    """
    import re

    if backup_dir is None:
        backup_dir = _get_default_backup_dir()
    else:
        backup_dir = Path(backup_dir).resolve()

    # Check directory exists
    if not backup_dir.exists():
        return []

    if not backup_dir.is_dir():
        raise BackupIOError(f"Not a directory: {backup_dir}")

    # Find backup files
    pattern = f"{BACKUP_FILENAME_PREFIX}*{BACKUP_EXTENSION}"
    backup_files = list(backup_dir.glob(pattern))

    # Collect backup info
    backups: list[BackupInfo] = []

    for path in backup_files:
        try:
            archive_size = path.stat().st_size
        except OSError as e:
            logger.warning("Failed to read backup file %s: %s", path, e)
            continue

        # Try to extract metadata
        metadata: BackupMetadata | None = None
        created_at: str = ""

        try:
            metadata = _read_backup_metadata(path)
            created_at = metadata.created_at
        except (BackupValidationError, BackupIOError) as e:
            logger.debug("Failed to read metadata from %s: %s", path, e)
            # Try to extract timestamp from filename
            match = re.search(
                rf"{BACKUP_FILENAME_PREFIX}(\d{{4}}-\d{{2}}-\d{{2}}T\d{{6}}Z)",
                path.name,
            )
            if match:
                # Convert YYYYMMDDTHHMMSSZ to ISO-8601
                ts = match.group(1)
                created_at = f"{ts[:10]}T{ts[11:13]}:{ts[13:15]}:{ts[15:17]}Z"
            else:
                # Use file modification time as fallback
                mtime = path.stat().st_mtime
                created_at = datetime.fromtimestamp(mtime, UTC).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )

        backups.append(
            BackupInfo(
                path=path,
                filename=path.name,
                created_at=created_at,
                archive_size_bytes=archive_size,
                metadata=metadata,
            )
        )

    # Sort by creation date (newest first)
    backups.sort(key=lambda b: b.created_at, reverse=True)

    return backups
