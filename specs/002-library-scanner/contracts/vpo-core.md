# Interface Contract: vpo-core (Rust Extension)

**Feature**: 002-library-scanner
**Date**: 2025-11-21

## Overview

The `vpo-core` Rust library provides performance-critical functionality exposed to Python via PyO3 bindings. It is compiled as a native extension and imported as `vpo._core`.

## Module Structure

```python
# vpo/_core.pyi (type stubs)

from typing import NamedTuple

class FileHash(NamedTuple):
    """Result of hashing a single file."""
    path: str
    hash: str | None      # None if error occurred
    error: str | None     # Error message if hash is None

class DiscoveredFile(NamedTuple):
    """A discovered video file with basic metadata."""
    path: str
    size: int             # File size in bytes
    modified: float       # Unix timestamp (seconds since epoch)

def discover_videos(
    roots: list[str],
    extensions: list[str],
    follow_symlinks: bool = True,
    skip_hidden: bool = True,
) -> list[DiscoveredFile]:
    """
    Recursively discover video files in the given directories.

    Uses parallel directory traversal for performance.

    Args:
        roots: List of directory paths to scan
        extensions: List of file extensions to match (without dot, e.g., ["mkv", "mp4"])
        follow_symlinks: Whether to follow symbolic links (default: True)
        skip_hidden: Whether to skip hidden files/directories (default: True)

    Returns:
        List of DiscoveredFile tuples for all matching files

    Raises:
        OSError: If a root directory doesn't exist or isn't accessible
    """
    ...

def hash_files(
    paths: list[str],
    chunk_size: int = 65536,
    num_threads: int | None = None,
) -> list[FileHash]:
    """
    Compute content hashes for multiple files in parallel.

    Uses partial hashing (first chunk + last chunk + size) for performance.

    Args:
        paths: List of file paths to hash
        chunk_size: Size of chunks to read (default: 64KB)
        num_threads: Number of threads (default: CPU count)

    Returns:
        List of FileHash tuples in same order as input paths.
        Files that couldn't be hashed have hash=None and error set.

    Note:
        Hash format: "xxh64:{first_hash}:{last_hash}:{size}"
        For files smaller than 2*chunk_size, entire file is hashed.
    """
    ...

def version() -> str:
    """Return the vpo-core library version."""
    ...
```

## Hash Format Specification

The content hash uses the following format:

```
xxh64:{first_chunk_hash}:{last_chunk_hash}:{file_size}
```

**Components**:
- `xxh64`: Algorithm identifier
- `first_chunk_hash`: xxHash64 of first N bytes (hex, lowercase)
- `last_chunk_hash`: xxHash64 of last N bytes (hex, lowercase)
- `file_size`: File size in bytes (decimal)

**Examples**:
```
xxh64:a1b2c3d4e5f67890:0987654321fedcba:8589934592
xxh64:deadbeef12345678:deadbeef12345678:1024
```

**Edge Cases**:
- File size < chunk_size: Hash entire file, first == last
- File size < 2*chunk_size: Chunks may overlap, that's OK
- Empty file: `xxh64:ef46db3751d8e999:ef46db3751d8e999:0` (xxh64 of empty input)

## Error Handling

The Rust functions handle errors gracefully:

### discover_videos

| Condition | Behavior |
|-----------|----------|
| Root doesn't exist | Raises `OSError` |
| Root isn't a directory | Raises `OSError` |
| Permission denied on subdirectory | Skips that subtree, continues |
| Symlink cycle detected | Skips, continues |
| File disappeared during scan | Skips, continues |

### hash_files

| Condition | Behavior |
|-----------|----------|
| File doesn't exist | Returns FileHash with error="File not found" |
| Permission denied | Returns FileHash with error="Permission denied" |
| I/O error | Returns FileHash with error=<error message> |
| Empty paths list | Returns empty list |

## Thread Safety

- All functions are thread-safe and can be called from multiple Python threads
- The Rust code releases the GIL during I/O operations
- `hash_files` uses an internal rayon thread pool (configurable via `num_threads`)
- `discover_videos` uses rayon for parallel directory traversal

## Performance Characteristics

### discover_videos
- Parallelizes across directory branches
- Memory: O(number of matching files)
- Typical: 100,000 files in ~2 seconds on SSD

### hash_files
- Parallelizes across files
- I/O bound for spinning disks, CPU bound for fast SSDs
- Memory: O(chunk_size * num_threads)
- Typical: 10,000 8GB files in ~30 seconds on SSD (partial hash)

## Rust Implementation Notes

### Cargo.toml

```toml
[package]
name = "vpo-core"
version = "0.1.0"
edition = "2021"

[lib]
name = "vpo_core"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.22", features = ["extension-module"] }
rayon = "1.10"
xxhash-rust = { version = "0.8", features = ["xxh64"] }
walkdir = "2.5"
```

### lib.rs Structure

```rust
use pyo3::prelude::*;

mod discovery;
mod hasher;

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(discovery::discover_videos, m)?)?;
    m.add_function(wrap_pyfunction!(hasher::hash_files, m)?)?;
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_class::<discovery::DiscoveredFile>()?;
    m.add_class::<hasher::FileHash>()?;
    Ok(())
}

#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}
```

## Testing Contract

Python tests for the Rust extension:

```python
import pytest
from vpo._core import discover_videos, hash_files, FileHash

class TestDiscoverVideos:
    def test_finds_mkv_files(self, tmp_path):
        (tmp_path / "movie.mkv").touch()
        (tmp_path / "show.mp4").touch()
        (tmp_path / "doc.txt").touch()

        results = discover_videos([str(tmp_path)], ["mkv", "mp4"])

        assert len(results) == 2
        paths = {r.path for r in results}
        assert str(tmp_path / "movie.mkv") in paths
        assert str(tmp_path / "show.mp4") in paths

    def test_recursive_discovery(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        (nested / "deep.mkv").touch()

        results = discover_videos([str(tmp_path)], ["mkv"])

        assert len(results) == 1
        assert results[0].path == str(nested / "deep.mkv")

    def test_skips_hidden_by_default(self, tmp_path):
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "secret.mkv").touch()
        (tmp_path / "visible.mkv").touch()

        results = discover_videos([str(tmp_path)], ["mkv"])

        assert len(results) == 1
        assert "visible.mkv" in results[0].path

    def test_nonexistent_root_raises(self):
        with pytest.raises(OSError):
            discover_videos(["/nonexistent/path"], ["mkv"])


class TestHashFiles:
    def test_hashes_file(self, tmp_path):
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"x" * 1000)

        results = hash_files([str(test_file)])

        assert len(results) == 1
        assert results[0].path == str(test_file)
        assert results[0].hash is not None
        assert results[0].hash.startswith("xxh64:")
        assert results[0].error is None

    def test_handles_missing_file(self, tmp_path):
        missing = str(tmp_path / "missing.bin")

        results = hash_files([missing])

        assert len(results) == 1
        assert results[0].path == missing
        assert results[0].hash is None
        assert "not found" in results[0].error.lower()

    def test_preserves_order(self, tmp_path):
        files = [tmp_path / f"file{i}.bin" for i in range(5)]
        for f in files:
            f.write_bytes(b"data")

        paths = [str(f) for f in files]
        results = hash_files(paths)

        assert [r.path for r in results] == paths

    def test_hash_format(self, tmp_path):
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"hello world")

        results = hash_files([str(test_file)])

        hash_value = results[0].hash
        parts = hash_value.split(":")
        assert len(parts) == 4
        assert parts[0] == "xxh64"
        assert len(parts[1]) == 16  # xxh64 hex = 16 chars
        assert len(parts[2]) == 16
        assert parts[3] == "11"  # len("hello world")
```

## Usage Example

```python
from vpo._core import discover_videos, hash_files

# Discover all video files
files = discover_videos(
    roots=["/media/movies", "/media/tv"],
    extensions=["mkv", "mp4", "avi"],
)
print(f"Found {len(files)} video files")

# Hash them in parallel
paths = [f.path for f in files]
hashes = hash_files(paths)

# Process results
for file_info, hash_result in zip(files, hashes):
    if hash_result.error:
        print(f"Error hashing {file_info.path}: {hash_result.error}")
    else:
        print(f"{file_info.path}: {hash_result.hash}")
```
