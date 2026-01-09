# Research: Library Scanner

**Feature**: 002-library-scanner
**Date**: 2025-11-21

## Research Summary

This document captures technical decisions and research findings for implementing the library scanner.

---

## R1: CLI Framework Selection

**Decision**: Use `click` for CLI implementation

**Rationale**:
- Industry standard for Python CLI applications
- Declarative command/option syntax reduces boilerplate
- Built-in support for nested commands (future: `vpo inspect`, `vpo apply`)
- Excellent testing support via `CliRunner`
- Already widely used in the Python ecosystem

**Alternatives Considered**:

| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| argparse (stdlib) | No dependency | Verbose; manual subcommand setup | More boilerplate; worse testing story |
| typer | Modern; type hints | Dependency on click anyway | Unnecessary abstraction layer |
| fire | Zero config | Less control; magic behavior | Unpredictable CLI interface |

---

## R2: Content Hash Algorithm

**Decision**: Use xxHash (xxh64) via `xxhash` library with partial file hashing

**Rationale**:
- xxHash is ~10x faster than SHA-256 for large files
- Partial hashing (first 64KB + last 64KB + file size) provides good uniqueness for media files while keeping scan time reasonable
- Already proven in media management tools (Plex, Emby use similar approaches)

**Alternatives Considered**:

| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| SHA-256 | Cryptographic; stdlib | Slow for large files | 8GB file = ~30s vs ~1s for xxHash |
| MD5 | Fast; stdlib | Collision-prone; deprecated | Security concerns even for non-crypto use |
| Full file hash | Most accurate | Very slow | 10,000 files × 8GB = impractical |

**Implementation Notes**:
- Hash format: `xxh64:<first_chunk>:<last_chunk>:<size>`
- Chunk size: 64KB (65536 bytes)
- Fallback: If file < 128KB, hash entire file

---

## R3: Database Schema Design

**Decision**: Normalized schema with files and tracks tables; use sqlite3 stdlib

**Rationale**:
- SQLite is embedded, zero-config, and perfect for single-user desktop tools
- Normalized schema (files → tracks one-to-many) matches domain model
- stdlib `sqlite3` avoids ORM complexity while providing adequate functionality
- Dataclasses for Python-side models provide type safety without framework

**Alternatives Considered**:

| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| SQLAlchemy | Full ORM; migrations | Heavy dependency; complexity | Overkill for simple schema |
| Peewee | Lightweight ORM | Still an abstraction layer | Unnecessary for 4 tables |
| TinyDB | Document store | No SQL queries | Harder to query by attributes |

**Implementation Notes**:
- Use `CREATE TABLE IF NOT EXISTS` for auto-initialization
- Store schema version in `_meta` table for future migrations
- Use `INSERT OR REPLACE` (upsert) for idempotent re-scanning

---

## R4: Directory Traversal Strategy

**Decision**: Use `pathlib.Path.rglob()` with symlink handling

**Rationale**:
- `pathlib` is modern, cross-platform, and stdlib
- `rglob()` provides recursive globbing with minimal code
- Symlink cycle detection via `Path.resolve()` and visited set

**Alternatives Considered**:

| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| os.walk | Traditional; well-known | More verbose; no glob | More code for same result |
| glob.glob | Simple | No recursive by default | Requires `**` and followlinks handling |
| scandir | Fast | Lower-level; manual recursion | Premature optimization |

**Implementation Notes**:
- Default extensions: `.mkv`, `.mp4`, `.avi`, `.webm`, `.m4v`, `.mov`
- Case-insensitive matching (`.MKV` == `.mkv`)
- Skip hidden directories (`.cache`, `.Trash`)

---

## R5: MediaIntrospector Interface Design

**Decision**: Protocol-based interface with stub implementation

**Rationale**:
- Python Protocol (typing.Protocol) enables structural typing without inheritance
- Stub returns placeholder data for Sprint 1; real implementation in future sprint
- Clean separation allows testing scanner without ffprobe dependency

**Alternatives Considered**:

| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| ABC (abstract base class) | Explicit contract | Requires inheritance | Less Pythonic; more coupling |
| Duck typing only | Flexible | No static checking | Harder to maintain contract |
| Direct ffprobe calls | Works now | Tight coupling | Blocks testing; Sprint 1 scope |

**Implementation Notes**:
- `MediaIntrospector` Protocol with `get_file_info(path: Path) -> FileInfo`
- `FileInfo` dataclass with nested `TrackInfo` list
- Stub returns container format inferred from extension

---

## R6: Error Handling Strategy

**Decision**: Log errors and continue; accumulate in summary

**Rationale**:
- Large library scans should not abort on single file errors
- Users expect summary of what succeeded and what failed
- Logging provides audit trail for troubleshooting

**Alternatives Considered**:

| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| Fail-fast | Simple; clear | One bad file stops everything | Unacceptable for library scans |
| Silent skip | Non-disruptive | User unaware of issues | Leads to confusion |
| Interactive prompts | User control | Not scriptable | Breaks automation use cases |

**Implementation Notes**:
- Errors stored in scan result object
- Summary shows: `X files scanned, Y errors (see log)`
- `--verbose` flag shows errors inline

---

## R7: Database Location

**Decision**: `~/.vpo/library.db` with `--db` override option

**Rationale**:
- XDG-style user data directory (`~/.vpo/`)
- Follows convention of similar tools (yt-dlp, gallery-dl)
- Override flag enables testing and multi-library scenarios

**Alternatives Considered**:

| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| Current directory | Obvious | Pollutes project dirs | Unexpected behavior |
| XDG_DATA_HOME | Standards-compliant | Complex; varies by OS | Overkill for MVP |
| In-memory only | Fast tests | No persistence | Defeats purpose |

---

## R8: Parallelism Strategy

**Decision**: Hybrid Python/Rust architecture with Rust handling performance-critical tasks

**Rationale**:
- Python's GIL limits CPU-bound parallelism for hashing large files
- Large library scans (terabytes, 10,000+ files) require true parallelism
- Rust provides: zero-cost abstractions, fearless concurrency via rayon, no GIL
- Python remains ideal for: CLI, database operations, orchestration, future ffprobe integration
- PyO3/maturin provides seamless Python-Rust interop with minimal overhead

**Alternatives Considered**:

| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| Python multiprocessing | Pure Python; bypasses GIL | IPC overhead; memory duplication; complexity | Significant overhead for fine-grained parallelism |
| Python ThreadPoolExecutor | Simple | GIL limits CPU parallelism | Doesn't solve the core problem |
| asyncio | Good for network I/O | Less benefit for disk I/O; complexity | Not suited for CPU-bound hashing |
| Pure Rust binary | Maximum performance | Two separate tools; IPC overhead | Loses Python ecosystem benefits |

**Implementation Notes**:
- Rust library `vpo-core` handles: parallel directory discovery, parallel file hashing
- Uses `rayon` for work-stealing thread pool (automatically scales to CPU cores)
- Uses `walkdir` for efficient directory traversal
- Uses `xxhash-rust` for xxh64 hashing (same algorithm, native speed)
- Python calls Rust via PyO3 bindings compiled with maturin
- Rust returns results as Python-native types (lists, strings)

**Performance Expectations**:
- 10,000 files on SSD: ~30 seconds (vs ~5 minutes single-threaded Python)
- Disk I/O will remain the bottleneck for spinning disks/NAS
- Scales linearly with CPU cores for local SSD workloads

---

## Dependencies Summary

### Rust Crate (crates/vpo-core/Cargo.toml)

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

### Python Runtime Dependencies

```toml
dependencies = [
    "click>=8.0",
]
# Note: xxhash Python package no longer needed - using Rust xxhash-rust
# Note: vpo-core is built as native extension via maturin
```

### Build System (pyproject.toml)

```toml
[build-system]
requires = ["maturin>=1.7"]
build-backend = "maturin"

[tool.maturin]
features = ["pyo3/extension-module"]
module-name = "vpo._core"
```

### Development Dependencies

```toml
dev = [
    "ruff>=0.14.5",
    "pytest>=9.0.1",
    "maturin>=1.7",
]
```
