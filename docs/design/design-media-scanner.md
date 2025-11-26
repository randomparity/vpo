# Media Scanner Design

**Purpose:**
This document describes how VPO's directory scanner works, including file discovery, hashing, incremental scanning, and the hybrid Python/Rust architecture.

---

## Overview

The media scanner is responsible for:
1. Discovering video files in directories
2. Computing content hashes for change detection
3. Extracting metadata via introspection
4. Persisting results to the database

The scanner uses a hybrid architecture: Rust handles high-performance file discovery and hashing, while Python orchestrates the workflow and database operations.

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                     ScannerOrchestrator (Python)                 │
│                                                                  │
│  - Coordinates discovery, hashing, and persistence               │
│  - Handles signal interruption (Ctrl+C)                          │
│  - Manages incremental scan logic                                │
└────────────────────────┬────────────────────────────────────────┘
                         │
           ┌─────────────┴─────────────┐
           ▼                           ▼
┌─────────────────────┐     ┌─────────────────────┐
│   vpo-core (Rust)    │     │  FFprobeIntrospector │
│                      │     │      (Python)        │
│  - discover_videos() │     │                      │
│  - hash_files()      │     │  - get_file_info()   │
└─────────────────────┘     └─────────────────────┘
```

---

## Rust Core Functions

### `discover_videos(directory, extensions, follow_symlinks)`

Recursively discovers video files in a directory.

**Parameters:**
- `directory`: Path to scan
- `extensions`: List of file extensions (e.g., `["mkv", "mp4"]`)
- `follow_symlinks`: Whether to follow symbolic links

**Returns:** List of dictionaries with file info:
```python
{
    "path": "/media/movies/movie.mkv",
    "size": 4831838208,
    "modified": 1705312200.0  # Unix timestamp
}
```

**Behavior:**
- Skips hidden files and directories (starting with `.`)
- Handles permission errors gracefully
- Reports symlinks that would create cycles

### `hash_files(paths)`

Computes partial content hashes for a list of files.

**Parameters:**
- `paths`: List of file paths to hash

**Returns:** List of dictionaries:
```python
{
    "path": "/media/movies/movie.mkv",
    "hash": "xxh64:a1b2c3d4:e5f6a7b8:4831838208",
    "error": None  # or error message
}
```

**Hash Format:** `xxh64:<head_hash>:<tail_hash>:<file_size>`
- `head_hash`: xxHash64 of first 64KB
- `tail_hash`: xxHash64 of last 64KB
- `file_size`: Total file size in bytes

---

## Incremental Scanning

The scanner avoids reprocessing unchanged files:

### Skip Conditions

A file is skipped (not reprocessed) if:
1. It exists in the database, AND
2. Its modification time hasn't changed

### Processing Logic

```python
for file in discovered_files:
    existing = get_file_by_path(conn, file.path)
    if existing is None:
        # New file - process it
        files_to_process.append(file)
    elif existing.modified_at != file.modified_at.isoformat():
        # Modified file - process it
        files_to_process.append(file)
    else:
        # Unchanged - skip
        result.files_skipped += 1
```

---

## Signal Handling

The scanner supports graceful interruption via Ctrl+C:

```python
class ScannerOrchestrator:
    def __init__(self):
        self._interrupt_event = threading.Event()

    def scan_and_persist(self, ...):
        # Install signal handler
        old_handler = signal.signal(signal.SIGINT, self._create_signal_handler())

        try:
            for file in files_to_process:
                if self._is_interrupted():
                    result.interrupted = True
                    break
                # Process file...
        finally:
            # Restore original handler
            signal.signal(signal.SIGINT, old_handler)
```

When interrupted:
- Current file finishes processing
- Partial results are saved to database
- Exit code 130 is returned

---

## File Extensions

Default extensions: `mkv`, `mp4`, `avi`, `webm`, `m4v`, `mov`

Custom extensions can be specified via CLI:
```bash
vpo scan --extensions mkv,mp4,ts,m2ts /media/videos
```

Extension matching is case-insensitive.

---

## Introspection Integration

After discovery and hashing, the scanner optionally extracts metadata:

```python
# Auto-detect introspector
if FFprobeIntrospector.is_available():
    introspector = FFprobeIntrospector()
else:
    introspector = StubIntrospector()

# For each file
result = introspector.get_file_info(path)
container_format = result.container_format
tracks = result.tracks
```

If introspection fails for a file, the scanner logs a warning and continues without track metadata.

---

## Error Handling

### Discovery Errors

Errors during directory traversal are collected and reported:
```python
except (FileNotFoundError, NotADirectoryError) as e:
    result.errors.append((str(directory), str(e)))
```

### Hash Errors

Hash failures (e.g., permission denied) are recorded per-file:
```python
{
    "path": "/media/protected.mkv",
    "hash": None,
    "error": "Permission denied"
}
```

### Introspection Errors

Introspection failures don't stop the scan:
```python
try:
    result = introspector.get_file_info(path)
except MediaIntrospectionError as e:
    logger.warning("Introspection failed for %s: %s", path, e)
    # Continue without track data
```

---

## Performance Considerations

### Rust Core Benefits

- **Parallel I/O**: File discovery and hashing use multiple threads
- **Efficient hashing**: xxHash is much faster than cryptographic hashes
- **Partial hashing**: Only 128KB read per file (first + last 64KB)

### Progress Reporting

Progress is reported every 100 files to avoid overhead:
```python
if progress_callback and processed % 100 == 0:
    progress_callback(processed, total_to_process)
```

---

## Data Flow

```text
1. CLI invokes scan command
           │
           ▼
2. ScannerOrchestrator.scan_and_persist()
           │
           ├──► discover_videos() [Rust]
           │           │
           │           ▼
           │    List of (path, size, modified)
           │
           ├──► Check database for existing files
           │           │
           │           ▼
           │    Filter to new/modified files only
           │
           ├──► hash_files() [Rust]
           │           │
           │           ▼
           │    Add content_hash to each file
           │
           ├──► FFprobeIntrospector.get_file_info() [Python]
           │           │
           │           ▼
           │    Extract container format and tracks
           │
           └──► upsert_file() + upsert_tracks_for_file()
                        │
                        ▼
                   Database updated
```

---

## Related docs

- [Design Docs Index](DESIGN_INDEX.md)
- [Architecture Overview](../overview/architecture.md)
- [Database Design](design-database.md)
- [CLI Usage](../usage/cli-usage.md)
