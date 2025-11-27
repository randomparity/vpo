# CLI Contract: vpo apply

**Command**: `vpo apply`
**Purpose**: Apply a policy to a media file (preview or execute changes)

## Synopsis

```
vpo apply --policy <policy_file> [--dry-run] [--keep-backup | --no-keep-backup] <target>
```

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `target` | PATH | Yes | Path to media file to process |

## Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--policy` | `-p` | PATH | Required | Path to YAML policy file |
| `--dry-run` | `-n` | flag | false | Preview changes without modifying file |
| `--keep-backup` | | flag | profile | Keep backup file after successful operation |
| `--no-keep-backup` | | flag | profile | Delete backup file after successful operation |
| `--json` | `-j` | flag | false | Output in JSON format |
| `--verbose` | `-v` | flag | false | Show detailed operation log |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (or dry-run completed) |
| 1 | General error |
| 10 | Policy validation error |
| 20 | Target file not found or not accessible |
| 30 | External tool not available (mkvpropedit/ffmpeg) |
| 40 | Operation failed (backup restored) |

## Output Formats

### Human-Readable (default)

**Dry-run with changes:**
```
Policy: /home/user/.vpo/policies/default.yaml (v1)
Target: /media/movies/example.mkv

Proposed changes:
  Track 1 (audio, eng): Set as default
  Track 2 (audio, jpn): Clear default flag
  Track 3 (subtitle, eng): Set title "English"
  Reorder: [0, 2, 1, 3, 4] → [0, 1, 2, 3, 4]

Summary: 4 changes (requires remux)

To apply these changes, run without --dry-run
```

**Dry-run with no changes:**
```
Policy: /home/user/.vpo/policies/default.yaml (v1)
Target: /media/movies/example.mkv

No changes required - file already matches policy.
```

**Apply success:**
```
Policy: /home/user/.vpo/policies/default.yaml (v1)
Target: /media/movies/example.mkv

Applied 4 changes in 2.3s
Backup: /media/movies/example.mkv.vpo-backup (kept)
```

**Apply failure:**
```
Policy: /home/user/.vpo/policies/default.yaml (v1)
Target: /media/movies/example.mkv

Error: mkvmerge failed with exit code 2
  Output: Error: The file 'example.mkv' could not be opened for reading.

Restored from backup: /media/movies/example.mkv.vpo-backup
```

### JSON Format (`--json`)

**Dry-run response:**
```json
{
  "status": "dry_run",
  "policy": {
    "path": "/home/user/.vpo/policies/default.yaml",
    "version": 1
  },
  "target": {
    "path": "/media/movies/example.mkv",
    "container": "mkv"
  },
  "plan": {
    "requires_remux": true,
    "actions": [
      {
        "action_type": "SET_DEFAULT",
        "track_index": 1,
        "track_type": "audio",
        "current_value": false,
        "desired_value": true
      },
      {
        "action_type": "CLEAR_DEFAULT",
        "track_index": 2,
        "track_type": "audio",
        "current_value": true,
        "desired_value": false
      },
      {
        "action_type": "REORDER",
        "track_index": null,
        "current_value": [0, 2, 1, 3, 4],
        "desired_value": [0, 1, 2, 3, 4]
      }
    ]
  }
}
```

**Apply success response:**
```json
{
  "status": "completed",
  "operation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "policy": {
    "path": "/home/user/.vpo/policies/default.yaml",
    "version": 1
  },
  "target": {
    "path": "/media/movies/example.mkv",
    "container": "mkv"
  },
  "actions_applied": 4,
  "duration_seconds": 2.3,
  "backup_path": "/media/movies/example.mkv.vpo-backup",
  "backup_kept": true
}
```

**Error response:**
```json
{
  "status": "failed",
  "operation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "error": {
    "code": "TOOL_EXECUTION_ERROR",
    "message": "mkvmerge failed with exit code 2",
    "details": "The file 'example.mkv' could not be opened for reading."
  },
  "restored_from_backup": true
}
```

## Examples

```bash
# Preview changes (dry-run)
vpo apply --policy ~/.vpo/policies/default.yaml --dry-run movie.mkv

# Apply changes
vpo apply --policy ./my-policy.yaml movie.mkv

# Apply and keep backup
vpo apply -p policy.yaml --keep-backup movie.mkv

# JSON output for scripting
vpo apply -p policy.yaml --dry-run --json movie.mkv | jq '.plan.actions'
```

## Error Messages

| Error | Message |
|-------|---------|
| Policy not found | `Policy file not found: {path}` |
| Policy invalid | `Policy validation failed: {field}: {message}` |
| Target not found | `Target file not found: {path}` |
| Unsupported format | `Unsupported container format: {format}` |
| Tool missing | `Required tool not available: {tool}. Install mkvtoolnix or ffmpeg.` |
| Permission denied | `Cannot write to file: {path}. Check permissions.` |
| Concurrent access | `File is being modified by another operation. Try again later.` |

## Behavior Notes

1. **Dry-run is non-destructive**: No files are modified, no backups created, no database records.

2. **Backup behavior**:
   - Default: Uses profile setting (`~/.vpo/config.yaml` → `backup.keep_after_success`)
   - `--keep-backup` / `--no-keep-backup` override profile setting for this operation

3. **Atomic operations**:
   - MKV reordering writes to temp file, then atomic rename
   - Backup created before any modification
   - On failure, original restored from backup

4. **Database logging**: All apply operations (not dry-run) are recorded in operations table.

5. **Container-specific behavior**:
   - MKV: Full support (reorder via mkvmerge, metadata via mkvpropedit)
   - MP4: Metadata only (flags, titles, language)
   - Other: Best-effort metadata via ffmpeg
