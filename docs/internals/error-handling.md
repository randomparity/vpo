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

**Location:** `src/vpo/introspector/interface.py`

```python
from vpo.introspector.interface import MediaIntrospectionError

try:
    result = introspector.get_file_info(path)
except MediaIntrospectionError as e:
    print(f"Could not parse file: {e}")
```

### `DatabaseLockedError`

Raised when the SQLite database is locked by another process.

**Location:** `src/vpo/db/connection.py`

```python
from vpo.db.connection import DatabaseLockedError

try:
    with get_connection(db_path) as conn:
        # database operations
except DatabaseLockedError as e:
    print(f"Database locked: {e}")
    print("Hint: Close other VPO instances or use a different --db path.")
```

---

## CLI Exit Codes

VPO uses a centralized exit code system defined in `src/vpo/cli/exit_codes.py`. Exit codes are organized into ranges by category for consistency across all commands.

### Exit Code Ranges

| Range | Category |
|-------|----------|
| `0` | Success |
| `1-9` | General errors |
| `10-19` | Validation errors (policy, config, input) |
| `20-29` | Target/file errors |
| `30-39` | Tool/dependency errors |
| `40-49` | Operation errors |
| `50-59` | Analysis errors |
| `60-69` | Warning states |

### Complete Exit Code Reference

| Code | Name | Description |
|------|------|-------------|
| `0` | `SUCCESS` | Operation completed successfully |
| `1` | `GENERAL_ERROR` | Unspecified error |
| `2` | `INTERRUPTED` | Operation interrupted (Ctrl+C / SIGINT) |
| `3` | `INVALID_ARGUMENTS` | Invalid CLI arguments |
| `10` | `POLICY_VALIDATION_ERROR` | Policy file validation failed |
| `11` | `CONFIG_ERROR` | Configuration error |
| `12` | `PROFILE_NOT_FOUND` | Specified profile not found |
| `20` | `TARGET_NOT_FOUND` | Target file or directory not found |
| `21` | `FILE_NOT_IN_DATABASE` | File not found in database |
| `22` | `NO_TRACKS_FOUND` | No tracks found in file |
| `30` | `TOOL_NOT_AVAILABLE` | Required external tool not available |
| `31` | `PLUGIN_UNAVAILABLE` | Required plugin not available |
| `32` | `FFPROBE_NOT_FOUND` | ffprobe not installed or not in PATH |
| `40` | `OPERATION_FAILED` | Operation failed during execution |
| `41` | `FILE_LOCKED` | File is locked by another process |
| `42` | `DATABASE_ERROR` | Database operation failed |
| `50` | `ANALYSIS_ERROR` | Analysis or classification failed |
| `51` | `PARSE_ERROR` | Failed to parse file |
| `60` | `WARNINGS` | Completed with warnings |
| `61` | `CRITICAL` | Critical issues detected |

### Exit Codes by Command

**`vpo scan`**: `SUCCESS`, `GENERAL_ERROR`, `INTERRUPTED`

**`vpo inspect`**: `SUCCESS`, `TARGET_NOT_FOUND`, `FFPROBE_NOT_FOUND`, `PARSE_ERROR`, `ANALYSIS_ERROR`

**`vpo classify`**: `SUCCESS`, `TARGET_NOT_FOUND`, `NO_TRACKS_FOUND`, `ANALYSIS_ERROR`

**`vpo doctor`**: `SUCCESS`, `WARNINGS`, `CRITICAL`

**`vpo process`**: `SUCCESS`, `GENERAL_ERROR`, `POLICY_VALIDATION_ERROR`, `TARGET_NOT_FOUND`, `TOOL_NOT_AVAILABLE`, `OPERATION_FAILED`

### Using Exit Codes in Code

```python
from vpo.cli.exit_codes import ExitCode

# Use the enum for type safety and clarity
sys.exit(ExitCode.TARGET_NOT_FOUND)

# The enum is an IntEnum, so it works with sys.exit()
if not path.exists():
    click.echo(f"Error: File not found: {path}", err=True)
    sys.exit(ExitCode.TARGET_NOT_FOUND)
```

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

From `src/vpo/cli/scan.py`:

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
