# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Video Policy Orchestrator (VPO) is a spec-driven tool for scanning, organizing, and transforming video libraries using user-defined policies. The project analyzes media files and applies YAML policies to normalize track ordering, metadata, language tags, and more.

## Build & Test Commands

```bash
# Install dependencies (use uv, not pip)
uv pip install -e ".[dev]"

# Build Rust extension (required after pulling or modifying Rust code)
uv run maturin develop

# Run tests
uv run pytest                           # All tests
uv run pytest tests/unit/               # Unit tests only
uv run pytest -k test_name              # Single test by name
uv run pytest tests/path/to_file.py    # Single test file

# Linting & formatting
uv run ruff check .                     # Python lint
uv run ruff format .                    # Python format
cargo clippy --manifest-path crates/vpo-core/Cargo.toml  # Rust lint
cargo fmt --manifest-path crates/vpo-core/Cargo.toml     # Rust format

# Run CLI
uv run vpo --help
uv run vpo scan /path/to/videos
uv run vpo inspect /path/to/file.mkv
uv run vpo apply --policy policy.yaml /path/to/file.mkv --dry-run
```

## Tech Stack

- **Python 3.10+** with click (CLI), pydantic, PyYAML
- **Rust** (PyO3/maturin) for parallel file discovery and hashing in `crates/vpo-core/`
- **SQLite** database at `~/.vpo/library.db`
- **External tools:** ffprobe (introspection), mkvpropedit/mkvmerge (MKV editing), ffmpeg (metadata editing)

## Architecture

```
src/video_policy_orchestrator/
├── cli/           # Click commands: scan, inspect, apply, doctor
├── db/            # SQLite schema, models (FileInfo, TrackInfo), operations
├── introspector/  # MediaIntrospector protocol, ffprobe implementation
├── policy/        # PolicySchema loading, Plan evaluation, track matchers
├── executor/      # Tool executors: mkvpropedit, mkvmerge, ffmpeg_metadata
├── config/        # Configuration loading and models
├── scanner/       # Orchestrates discovery and introspection
└── tools/         # External tool detection and capability caching

crates/vpo-core/   # Rust extension for parallel discovery/hashing
```

**Key data flows:**
1. `scan` → discovers files (Rust) → introspects via ffprobe → stores in SQLite
2. `inspect` → reads file from DB or live introspection → displays track info
3. `apply` → loads policy YAML → evaluates against file → produces Plan → executes via mkvpropedit/ffmpeg

## Development Guidelines

- Prefer explicit, well-typed dataclasses/models over dicts
- Preserve existing patterns for time handling (UTC), IDs, logging, and config
- No local-time datetime storage, hardcoded paths, ad-hoc subprocess calls, or inline SQL in business logic
- Before finalizing: check idempotence, error handling, logging/auditability, and tests

## Development Methodology

This project uses **spec-driven development**:
1. Features start as specs in `docs/overview/` and detailed specs in `specs/`
2. Implementation follows specs with test-driven development
3. Use `/speckit.*` commands for feature planning and implementation

## Documentation Rules

- Documentation goes in `/docs/` only; root allows only README.md, CLAUDE.md, CONTRIBUTING.md
- Doc types: Overview, Usage/How-to, Design/Internals, Decision (ADR), Reference
- Prefer updating existing docs over creating new ones
- Every new doc must be added to `/docs/INDEX.md` and include a "Related docs" section
- Keep docs small and focused; link instead of duplicating content

## Active Technologies
- Python 3.10+ (matching existing codebase) + click (CLI), pydantic (validation), PyYAML (config), importlib.metadata (entry points) (005-plugin-architecture)
- SQLite (~/.vpo/library.db for plugin acknowledgment records) (005-plugin-architecture)

## Recent Changes
- 005-plugin-architecture: Added Python 3.10+ (matching existing codebase) + click (CLI), pydantic (validation), PyYAML (config), importlib.metadata (entry points)
