# Data Model: Library Backup and Restore

**Feature**: 045-library-backup
**Date**: 2026-02-05

## Entities

### BackupMetadata

Metadata stored alongside the database in backup archives.

```python
@dataclass(frozen=True)
class BackupMetadata:
    """Metadata describing a backup archive."""

    vpo_version: str
    """VPO version that created the backup (e.g., "1.0.0")."""

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
```

### BackupInfo

Information about an existing backup file for listing.

```python
@dataclass(frozen=True)
class BackupInfo:
    """Information about a backup file."""

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
```

### BackupResult

Result of a backup operation.

```python
@dataclass(frozen=True)
class BackupResult:
    """Result of a backup operation."""

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
```

### RestoreResult

Result of a restore operation.

```python
@dataclass(frozen=True)
class RestoreResult:
    """Result of a restore operation."""

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
```

## Error Types

```python
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
```

## Archive Format

```
{backup_filename}.tar.gz
├── library.db              # SQLite database (complete copy)
└── backup_metadata.json    # BackupMetadata serialized as JSON
```

**Internal filenames are fixed** - extraction replaces whatever exists in the target.

## Validation Rules

1. **BackupMetadata.created_at**: Must be valid ISO-8601 UTC timestamp
2. **BackupMetadata.schema_version**: Must be positive integer
3. **BackupMetadata.database_size_bytes**: Must be non-negative
4. **Archive integrity**: Must contain both `library.db` and `backup_metadata.json`
5. **Database integrity**: Extracted `library.db` must pass SQLite quick_check

## State Transitions

No persistent state changes to database schema. Backup/restore operations work with complete database snapshots.

**Restore flow**:
1. Archive → (validate) → Temp extraction
2. Temp DB → (integrity check) → Verified
3. Verified → (atomic rename) → Active database

**Backup flow**:
1. Active DB → (online backup API) → Temp copy
2. Temp copy + Metadata → (tar + gzip) → Archive
3. Archive → (move to destination) → Complete
