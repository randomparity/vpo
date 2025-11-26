# Error Handling

**Purpose:**
This document describes VPO's error handling patterns, custom exceptions, exit codes, and strategies for dealing with failures.

---

## Overview

VPO follows these principles for error handling:
1. **Fail gracefully**: Continue processing when possible, collect errors for reporting
2. **Clear exit codes**: Different exit codes for different failure modes
3. **Custom exceptions**: Domain-specific exception classes for typed error handling
4. **User-friendly messages**: Clear error messages with hints for resolution

---

## Custom Exceptions

### `MediaIntrospectionError`

Raised when ffprobe fails to parse a media file.

**Location:** `src/video_policy_orchestrator/introspector/interface.py`

```python
from video_policy_orchestrator.introspector.interface import MediaIntrospectionError

try:
    result = introspector.get_file_info(path)
except MediaIntrospectionError as e:
    print(f"Could not parse file: {e}")
```

### `DatabaseLockedError`

Raised when the SQLite database is locked by another process.

**Location:** `src/video_policy_orchestrator/db/connection.py`

```python
from video_policy_orchestrator.db.connection import DatabaseLockedError

try:
    with get_connection(db_path) as conn:
        # database operations
except DatabaseLockedError as e:
    print(f"Database locked: {e}")
    print("Hint: Close other VPO instances or use a different --db path.")
```

---

## CLI Exit Codes

### `vpo scan`

| Code | Meaning |
|------|---------|
| `0` | Success (all files processed, or partial success with some errors) |
| `1` | Complete failure (errors occurred and no files were found) |
| `130` | Interrupted by Ctrl+C (partial results saved) |

### `vpo inspect`

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | File not found |
| `2` | ffprobe not installed or not in PATH |
| `3` | Failed to parse media file |

---

## Error Handling Strategies

### Fail Fast vs. Skip and Continue

**Fail Fast** is used for:
- Missing required dependencies (ffprobe not installed)
- Invalid command-line arguments
- Database locked errors
- File not found (for single-file operations)

**Skip and Continue** is used for:
- Individual file processing errors during batch scans
- Malformed media files in a library scan
- Non-fatal parsing warnings

### Example: Batch Scan Error Collection

From `src/video_policy_orchestrator/cli/scan.py`:

```python
# Errors are collected during scanning
result = scanner.scan_and_persist(directories, conn)

# Report errors after completion
if result.errors:
    click.echo(f"{len(result.errors)} error(s):", err=True)
    for path, error in result.errors[:5]:
        click.echo(f"  {path}: {error}", err=True)
    if len(result.errors) > 5:
        click.echo(f"  ... and {len(result.errors) - 5} more", err=True)

# Exit success if any files were processed
sys.exit(0 if files else 1)
```

### Signal Handling

The scanner supports graceful interruption via Ctrl+C:

```python
# Partial results are saved before exit
if result.interrupted:
    click.echo("\nScan interrupted. Partial results saved.", err=True)
    sys.exit(130)
```

---

## Error Output Patterns

### Human-Readable Errors

```text
Error: File not found: /media/movies/missing.mkv
```

```text
Error: ffprobe is not installed or not in PATH.
Install ffmpeg to use media introspection features.
```

### Errors with Hints

```text
Error: Database is locked by another process
Hint: Close other VPO instances or use a different --db path.
```

### JSON Error Output

```json
{
  "files_found": 10,
  "errors": [
    {"path": "/media/movies/corrupt.mkv", "error": "Invalid container format"}
  ]
}
```

---

## Adding New Error Types

When adding new error types:

1. Create a specific exception class in the relevant module
2. Document the exception in this file
3. Use appropriate exit codes in CLI commands
4. Provide user-friendly error messages with hints where possible

```python
class NewFeatureError(Exception):
    """Raised when the new feature encounters a specific problem."""
    pass
```

---

## Related docs

- [Documentation Index](../INDEX.md)
- [Design Docs Index](../design/DESIGN_INDEX.md)
- [CLI Usage](../usage/cli-usage.md)
- [Logging and Metrics](logging-and-metrics.md)
