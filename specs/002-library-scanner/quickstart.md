# Quickstart: Library Scanner

**Feature**: 002-library-scanner
**Date**: 2025-11-21

## Prerequisites

- Python 3.10+
- Rust 1.70+ (for native extension)
- uv package manager
- Git

### Installing Rust

If you don't have Rust installed:

```bash
# Install rustup (Rust toolchain manager)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Verify installation
rustc --version
cargo --version
```

## Setup

```bash
# Clone and enter repository
cd /path/to/vpo

# Checkout feature branch
git checkout 002-library-scanner

# Install maturin (Python-Rust build tool)
uv pip install maturin

# Build and install the package (compiles Rust extension)
uv pip install -e ".[dev]"

# Or build manually with maturin for development
maturin develop

# Verify installation
uv run python -c "from vpo._core import version; print(f'vpo-core: {version()}')"
```

## Project Structure After Implementation

```
# Rust native extension
crates/vpo-core/
├── Cargo.toml               # Rust package manifest
└── src/
    ├── lib.rs               # PyO3 module exports
    ├── discovery.rs         # Parallel directory traversal
    └── hasher.rs            # Parallel file hashing

# Python package
src/vpo/
├── __init__.py
├── _core.pyi                # Type stubs for Rust extension
├── cli/
│   ├── __init__.py
│   └── scan.py              # vpo scan command
├── db/
│   ├── __init__.py
│   ├── connection.py        # DB connection management
│   ├── models.py            # FileRecord, TrackRecord dataclasses
│   └── schema.py            # Schema creation
├── scanner/
│   ├── __init__.py
│   └── orchestrator.py      # Coordinates Rust core + DB
└── introspector/
    ├── __init__.py
    ├── interface.py         # MediaIntrospector protocol
    └── stub.py              # Stub implementation
```

## Running Tests

```bash
# Run all Python tests
uv run pytest

# Run with coverage
uv run pytest --cov=vpo

# Run only unit tests
uv run pytest tests/unit/

# Run only integration tests
uv run pytest tests/integration/

# Run tests for specific module
uv run pytest tests/unit/test_core.py -v

# Note: Rust unit tests for PyO3 extension modules cannot run standalone
# because they require Python linking. Test through Python instead:
uv run pytest tests/unit/test_core.py -v
```

## Using the Scanner

### Basic Usage

```bash
# Scan a directory
vpo scan /media/videos

# Scan multiple directories
vpo scan /media/movies /media/tv

# Preview without changes
vpo scan --dry-run /media/videos
```

### Configuration Options

```bash
# Custom extensions
vpo scan --extensions mkv,mp4 /media/videos

# Custom database location
vpo scan --db ~/my-library.db /media/videos

# Verbose output
vpo scan --verbose /media/videos

# JSON output
vpo scan --json /media/videos
```

### Querying the Database

```bash
# Open database directly
sqlite3 ~/.vpo/library.db

# Example queries
sqlite3 ~/.vpo/library.db "SELECT COUNT(*) FROM files;"
sqlite3 ~/.vpo/library.db "SELECT extension, COUNT(*) FROM files GROUP BY extension;"
sqlite3 ~/.vpo/library.db "SELECT path FROM files WHERE scan_status = 'error';"
```

## Development Workflow

### Adding New Functionality

1. Write failing test in `tests/unit/` or `tests/integration/`
2. Run tests to confirm failure: `uv run pytest tests/unit/test_new.py -v`
3. Implement minimal code to pass
4. Refactor if needed
5. Run full test suite: `uv run pytest`

### Code Quality

```bash
# Python lint
uv run ruff check .

# Python format
uv run ruff format .

# Fix auto-fixable issues
uv run ruff check --fix .

# Rust lint
cd crates/vpo-core && cargo clippy

# Rust format
cd crates/vpo-core && cargo fmt

# Rust format check (CI)
cd crates/vpo-core && cargo fmt --check
```

### Common Development Tasks

```bash
# Reset test database
rm -f ~/.vpo/library.db

# Test with temporary database
vpo scan --db /tmp/test.db /media/videos

# Debug with verbose logging
VPO_LOG_LEVEL=DEBUG vpo scan -v /media/videos
```

## Key Files to Understand

### Python

| File | Purpose |
|------|---------|
| `db/schema.py` | Database initialization and migrations |
| `db/models.py` | Dataclasses for File, Track records |
| `scanner/orchestrator.py` | Coordinates Rust core + DB writes |
| `introspector/interface.py` | MediaIntrospector protocol |
| `cli/scan.py` | CLI command implementation |
| `_core.pyi` | Type stubs for Rust extension |

### Rust (crates/vpo-core/src/)

| File | Purpose |
|------|---------|
| `lib.rs` | PyO3 module exports and Python bindings |
| `discovery.rs` | Parallel directory traversal with walkdir + rayon |
| `hasher.rs` | Parallel file hashing with xxhash-rust + rayon |

## Testing Fixtures

Test fixtures are in `tests/fixtures/`:

```
tests/fixtures/
└── sample_videos/
    ├── video.mkv       # Empty file with .mkv extension
    ├── video.mp4       # Empty file with .mp4 extension
    ├── nested/
    │   └── deep.mkv    # For recursion testing
    └── .hidden/
        └── hidden.mkv  # For hidden directory testing
```

## Troubleshooting

### "Command not found: vpo"

Ensure the package is installed with CLI entry point:
```bash
uv pip install -e "."
```

### "Database is locked"

Another process has the database open. Close other VPO instances or use a different `--db` path.

### "Permission denied" during scan

The scanner continues past permission errors. Use `--verbose` to see which files failed.

### Tests fail with "ModuleNotFoundError"

Install the package in development mode:
```bash
uv pip install -e ".[dev]"
```

### "cannot find -lpython3.x" during Rust build

Ensure Python development headers are installed:
```bash
# Ubuntu/Debian
sudo apt install python3-dev

# macOS (usually bundled with Python)
# Fedora
sudo dnf install python3-devel
```

### Rust extension not updating after code changes

Rebuild the extension:
```bash
maturin develop
```

### "error: linker `cc` not found" on Linux

Install build essentials:
```bash
sudo apt install build-essential
```

### Slow Rust compilation

Use release mode only for final testing:
```bash
# Debug mode (faster compile, slower runtime)
maturin develop

# Release mode (slower compile, faster runtime)
maturin develop --release
```
