# Research: Library Backup and Restore

**Feature**: 045-library-backup
**Date**: 2026-02-05

## SQLite Backup Approach

### Decision: Use `sqlite3.Connection.backup()` API

**Rationale**: The Python `sqlite3` module provides a `backup()` method that performs a safe, online backup of a database. This is safer than copying the file directly because:
- It handles WAL mode databases correctly
- It works even if there are active connections
- It provides progress reporting for large databases

**Alternatives considered**:
1. **File copy with shutil**: Simpler but risks corruption if database is in WAL mode or has active connections
2. **SQL dump**: Text format, not compressed well, slower to restore

### Implementation Pattern

```python
def backup_database(src_conn: sqlite3.Connection, dest_path: Path) -> None:
    """Backup database using online backup API."""
    dest_conn = sqlite3.connect(dest_path)
    with dest_conn:
        src_conn.backup(dest_conn)
    dest_conn.close()
```

## Archive Format

### Decision: tar.gz with metadata JSON

**Format structure**:
```
vpo-library-2026-02-05T143022Z.tar.gz
├── library.db              # The SQLite database
└── backup_metadata.json    # Backup info (schema version, etc.)
```

**Rationale**:
- `tarfile` is in stdlib, no dependencies
- gzip provides good compression for SQLite (typically 60-80% reduction)
- Separate metadata file allows inspection without full extraction

**Alternatives considered**:
1. **ZIP format**: Similar compression, but tar.gz is more common on Unix systems and VPO targets Linux/macOS
2. **Single file with embedded metadata**: Would require custom format, harder to inspect

## Backup Metadata Schema

### Decision: JSON metadata file

```json
{
  "vpo_version": "1.0.0",
  "schema_version": 27,
  "created_at": "2026-02-05T14:30:22Z",
  "database_size_bytes": 52428800,
  "file_count": 1523,
  "total_library_size_bytes": 1099511627776,
  "compression": "gzip"
}
```

**Rationale**: Human-readable, easy to parse, allows future extensibility

## Lock Detection

### Decision: Check for SQLite WAL lock file

**Approach**:
1. Check if `~/.vpo/library.db-wal` exists and has content
2. Check if `~/.vpo/library.db-shm` exists
3. Attempt to acquire EXCLUSIVE lock briefly to verify no active writers

**Rationale**: VPO daemon uses WAL mode. Presence of WAL files with content indicates active connections.

## Disk Space Check

### Decision: Use `shutil.disk_usage()`

**Approach**:
1. Get current database size
2. Estimate compressed size (database_size * 0.5 for gzip)
3. Check destination has at least 2x compressed size available
4. For restore: check database directory has enough space

**Rationale**: `shutil.disk_usage()` is stdlib and cross-platform

## Schema Version Compatibility

### Decision: Warn but allow restore of different schema versions

**Approach**:
1. Include schema version in backup metadata
2. On restore, compare backup schema version with current VPO schema version
3. If different, warn user but allow proceed with `--yes` flag
4. If backup schema is newer than installed VPO, refuse restore with error

**Rationale**: Users may restore to different machines. Downgrade restores are dangerous and should be blocked.

## Default Backup Location

### Decision: `~/.vpo/backups/`

**Rationale**: Follows existing VPO convention (`~/.vpo/` for all VPO data). Easy to back up entire VPO directory externally.

## Filename Format

### Decision: `vpo-library-{ISO8601_timestamp}.tar.gz`

**Example**: `vpo-library-2026-02-05T143022Z.tar.gz`

**Rationale**:
- Prefix `vpo-library-` makes purpose clear
- UTC timestamp ensures uniqueness and sortability
- `.tar.gz` extension makes format obvious

## Error Handling

### Decision: Custom exception hierarchy

```python
class BackupError(Exception):
    """Base class for backup errors."""

class BackupIOError(BackupError):
    """IO error during backup/restore."""

class BackupValidationError(BackupError):
    """Invalid or corrupted backup archive."""

class BackupSchemaError(BackupError):
    """Schema version incompatibility."""

class BackupLockError(BackupError):
    """Database is locked by another process."""
```

**Rationale**: Follows constitution principle VII (explicit error handling). Allows CLI to handle different errors appropriately.

## Atomic Restore

### Decision: Write to temp file, then atomic rename

**Approach**:
1. Extract database to temp file in same directory
2. Verify extracted database integrity (quick_check)
3. Close existing connection
4. Rename temp file over existing database (atomic on same filesystem)

**Rationale**: Prevents partial restore on failure. Maintains database integrity.
