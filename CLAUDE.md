# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Video Policy Orchestrator (VPO) is a spec-driven tool for scanning, organizing, and transforming video libraries using user-defined policies and an extensible plugin architecture. The project is in early development (pre-implementation).

## Development Methodology

This project uses **spec-driven development**:
1. Features start as specs in `docs/PRD.md` and `docs/ARCHITECTURE.md`
2. Detailed module specs live in `spec/`
3. Implementation follows specs with test-driven development

Use the Specify workflow commands (`/speckit.*`) for feature planning and implementation.

## Development Environment

- **Package Manager:** Use `uv` for all Python package operations (not pip)
  - Install: `uv pip install -e ".[dev]"`
  - Run tools: `uv run pytest`, `uv run ruff check .`

## Tech Stack (Planned)

- **Language:** Python
- **Database:** SQLite
- **External Tools:** ffmpeg/ffprobe, mkvmerge/mkvpropedit
- **Packaging:** pyproject.toml-based

## Architecture (Planned)

Key components:
- **CLI Frontend** - Commands: scan, inspect, apply, jobs, profiles
- **Core Engine** - Orchestrates scanning, policy evaluation, job scheduling, plugin calls
- **Media Introspector** - Wraps ffprobe/mkvmerge into uniform data model
- **Policy Engine** - Reads YAML/JSON policies, produces execution plans
- **Execution Layer & Job Queue** - Handles metadata edits, remuxes, transcodes, file moves
- **Plugin System** - Analyzer, Mutator, and Transcription plugins

## Active Technologies
- Python 3.10+ (minimum supported; CI will test 3.10, 3.11, 3.12) + ruff (linting/formatting), pytest (testing) (001-project-skeleton)
- N/A (infrastructure sprint, no data persistence) (001-project-skeleton)
- Python 3.10+ (per pyproject.toml) + click (CLI framework), dataclasses (data structures), sqlite3 (stdlib) (002-library-scanner)
- Rust 1.70+ with PyO3/maturin for native extension (vpo-core) providing parallel discovery and hashing (002-library-scanner)
- SQLite (~/.vpo/library.db) (002-library-scanner)

## Recent Changes
- 001-project-skeleton: Added Python 3.10+ (minimum supported; CI will test 3.10, 3.11, 3.12) + ruff (linting/formatting), pytest (testing)
- 002-library-scanner: Added hybrid Python/Rust architecture with maturin build system, click CLI, MediaIntrospector protocol
