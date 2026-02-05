# Quickstart: Library Backup and Restore

**Feature**: 045-library-backup
**Date**: 2026-02-05

## Overview

This feature adds backup and restore commands to `vpo library` for managing database snapshots.

## Quick Usage

### Create a Backup

```bash
# Default location (~/.vpo/backups/)
vpo library backup

# Custom location
vpo library backup --output /path/to/my-backup.tar.gz

# Preview without creating
vpo library backup --dry-run
```

### Restore from Backup

```bash
# Restore with confirmation prompt
vpo library restore /path/to/backup.tar.gz

# Restore without prompt
vpo library restore --yes /path/to/backup.tar.gz

# Validate only (don't restore)
vpo library restore --dry-run /path/to/backup.tar.gz
```

### List Backups

```bash
# List backups in default location
vpo library backups

# List backups in custom directory
vpo library backups --path /mnt/external/vpo-backups/
```

## Implementation Guide

### Module Location

```
src/vpo/db/backup.py     # Core backup/restore logic
src/vpo/cli/library.py   # CLI commands (extend existing)
```

### Key Functions

```python
# In db/backup.py

def create_backup(
    db_path: Path,
    output_path: Path | None = None,
) -> BackupResult:
    """Create a backup archive of the database."""

def restore_backup(
    backup_path: Path,
    db_path: Path,
    force: bool = False,
) -> RestoreResult:
    """Restore database from a backup archive."""

def list_backups(
    backup_dir: Path,
) -> list[BackupInfo]:
    """List available backups in a directory."""

def validate_backup(
    backup_path: Path,
) -> BackupMetadata:
    """Validate a backup archive and return its metadata."""
```

### Testing Strategy

1. **Unit tests** (`tests/unit/db/test_backup.py`):
   - BackupMetadata serialization/deserialization
   - Archive creation with mock database
   - Validation error cases

2. **Integration tests** (`tests/integration/cli/test_library_backup.py`):
   - Full backup/restore cycle with real database
   - CLI option parsing and output formats
   - Error handling (locked database, invalid archive)

### Dependencies

- Python stdlib only: `tarfile`, `json`, `shutil`, `sqlite3`
- Existing VPO: `click` (CLI), `vpo.db.schema` (schema version), `vpo.core` (utilities)

### Error Handling Pattern

```python
try:
    result = create_backup(db_path, output_path)
except BackupLockError:
    # Database locked by daemon
    click.echo("Database is locked. Stop the daemon first.", err=True)
    sys.exit(ExitCode.DATABASE_LOCKED)
except InsufficientSpaceError as e:
    # Not enough disk space
    click.echo(f"Insufficient disk space: {e}", err=True)
    sys.exit(ExitCode.INSUFFICIENT_SPACE)
except BackupIOError as e:
    # Generic IO error
    click.echo(f"Backup failed: {e}", err=True)
    sys.exit(ExitCode.OPERATION_FAILED)
```

## Next Steps

Run `/speckit.tasks` to generate implementation tasks.
