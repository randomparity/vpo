# CLI Contract: Library Backup Commands

**Feature**: 045-library-backup
**Date**: 2026-02-05

## Command: `vpo library backup`

Create a compressed backup of the library database.

### Usage

```bash
vpo library backup [OPTIONS]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--output`, `-o` | PATH | auto | Output path for backup file |
| `--dry-run` | FLAG | false | Show what would be backed up without creating archive |
| `--json` | FLAG | false | Output result as JSON |

### Behavior

1. If `--output` not specified, creates backup in `~/.vpo/backups/` with auto-generated timestamp filename
2. Creates parent directories if they don't exist
3. Collects metadata (schema version, file count, sizes)
4. Uses SQLite online backup API for consistency
5. Compresses with gzip

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 4 | Database locked |
| 5 | Insufficient disk space |

### Output (normal)

```
Backup created: /home/user/.vpo/backups/vpo-library-2026-02-05T143022Z.tar.gz
  Database size: 52.4 MB
  Archive size:  18.2 MB (65% compression)
  Files in library: 1,523
```

### Output (--json)

```json
{
  "success": true,
  "path": "/home/user/.vpo/backups/vpo-library-2026-02-05T143022Z.tar.gz",
  "archive_size_bytes": 19088384,
  "database_size_bytes": 52428800,
  "compression_ratio": 0.636,
  "file_count": 1523,
  "schema_version": 27,
  "created_at": "2026-02-05T14:30:22Z"
}
```

### Output (--dry-run)

```
Would create backup:
  Database: /home/user/.vpo/library.db (52.4 MB)
  Output: /home/user/.vpo/backups/vpo-library-2026-02-05T143022Z.tar.gz
  Estimated archive size: ~18-26 MB
  Files in library: 1,523
  Schema version: 27
```

---

## Command: `vpo library restore`

Restore the library database from a backup archive.

### Usage

```bash
vpo library restore [OPTIONS] BACKUP_FILE
```

### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `BACKUP_FILE` | PATH | Yes | Path to backup archive to restore |

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--yes`, `-y` | FLAG | false | Skip confirmation prompt |
| `--dry-run` | FLAG | false | Validate archive without restoring |
| `--json` | FLAG | false | Output result as JSON |

### Behavior

1. Validates archive integrity (structure, metadata, database)
2. Checks schema version compatibility
3. Prompts for confirmation (unless `--yes`)
4. Extracts to temp location, verifies, atomic rename
5. Warns if schema version differs from current VPO

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 3 | Invalid/corrupted archive |
| 4 | Database locked |
| 5 | Insufficient disk space |
| 6 | Schema version incompatible (backup newer than VPO) |

### Output (normal)

```
Restoring from: /path/to/vpo-library-2026-02-05T143022Z.tar.gz
  Created: 2026-02-05 14:30:22 UTC
  Files: 1,523
  Schema: v27

This will replace your current library database. Continue? [y/N] y

Restore complete.
  Database restored to: /home/user/.vpo/library.db
  Duration: 2.3 seconds
```

### Output (--dry-run)

```
Validating backup: /path/to/vpo-library-2026-02-05T143022Z.tar.gz

Archive valid:
  Created: 2026-02-05 14:30:22 UTC
  VPO version: 1.0.0
  Schema version: 27 (current: 27)
  Database size: 52.4 MB
  Files in backup: 1,523

No changes made (dry run).
```

### Output (schema mismatch warning)

```
⚠ Warning: Backup schema version (25) differs from current VPO schema (27).
  The database will be migrated after restore.

Continue anyway? [y/N]
```

---

## Command: `vpo library backups`

List available backups in the default backup directory.

### Usage

```bash
vpo library backups [OPTIONS]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--path`, `-p` | PATH | ~/.vpo/backups/ | Directory to scan for backups |
| `--json` | FLAG | false | Output as JSON |

### Behavior

1. Scans directory for `vpo-library-*.tar.gz` files
2. Reads metadata from each valid archive
3. Sorts by creation date (newest first)
4. Shows summary with size and file count

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (even if no backups found) |
| 1 | General error |

### Output (normal)

```
Backups in /home/user/.vpo/backups/:

Filename                                  Created              Size     Files
─────────────────────────────────────────────────────────────────────────────
vpo-library-2026-02-05T143022Z.tar.gz    2026-02-05 14:30    18.2 MB   1,523
vpo-library-2026-02-01T090000Z.tar.gz    2026-02-01 09:00    17.8 MB   1,498
vpo-library-2026-01-15T120000Z.tar.gz    2026-01-15 12:00    15.2 MB   1,201

Total: 3 backups (51.2 MB)
```

### Output (no backups)

```
No backups found in /home/user/.vpo/backups/

Create a backup with: vpo library backup
```

### Output (--json)

```json
{
  "directory": "/home/user/.vpo/backups",
  "total_count": 3,
  "total_size_bytes": 53687091,
  "backups": [
    {
      "filename": "vpo-library-2026-02-05T143022Z.tar.gz",
      "path": "/home/user/.vpo/backups/vpo-library-2026-02-05T143022Z.tar.gz",
      "created_at": "2026-02-05T14:30:22Z",
      "archive_size_bytes": 19088384,
      "database_size_bytes": 52428800,
      "file_count": 1523,
      "schema_version": 27
    }
  ]
}
```
