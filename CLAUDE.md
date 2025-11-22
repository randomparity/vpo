# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Video Policy Orchestrator (VPO) is a spec-driven tool for scanning, organizing, and transforming video libraries using user-defined policies and an extensible plugin architecture. The project is in early development (pre-implementation).

## Development Guidelines

- Prefer explicit, well-typed models over loosely structured dicts.
- Preserve and extend existing patterns for time handling, IDs, logging, and configuration rather than inventing new ones.
- Do not introduce local-time datetime storage, hardcoded paths, ad-hoc subprocess calls, or inline SQL in business logic.
- Before finalizing changes, review: (a) idempotence, (b) error handling, (c) logging/auditability, and (d) tests/fixtures for the new behavior.

## Development Methodology

This project uses **spec-driven development**:
1. Features start as specs in `docs/overview/project-overview.md` and `docs/overview/architecture.md`
2. Detailed module specs live in `specs/`
3. Implementation follows specs with test-driven development

Use the Specify workflow commands (`/speckit.*`) for feature planning and implementation.

## Development Environment

- **Package Manager:** Use `uv` for all Python package operations (not pip)
  - Install: `uv pip install -e ".[dev]"`
  - Run tools: `uv run pytest`, `uv run ruff check .`

## Tech Stack (Planned)

- **Language:** Python, Rust
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
- Python 3.10+ (per pyproject.toml) + click (CLI), subprocess (ffprobe invocation), sqlite3 (stdlib) (003-media-introspection)
- SQLite (~/.vpo/library.db) - existing schema from 002-library-scanner (003-media-introspection)
- Python 3.10+ (per pyproject.toml) + click (CLI), PyYAML (policy parsing), subprocess (mkvpropedit/ffmpeg invocation), sqlite3 (stdlib) (004-policy-engine)
- SQLite (~/.vpo/library.db) - existing schema extended for operation records (004-policy-engine)

## Documentation Rules

1. Allowed locations
- New documentation must be created under the /docs directory.
- The only Markdown files allowed at the repo root are:
- README.md (project overview)
- CLAUDE.md (agent instructions)
- CONTRIBUTING.md (contribution guidelines, if present)
- Do not create ad-hoc .md files in other directories (e.g. src/, scripts/, etc.).
2. Doc types
When creating or updating documentation, choose exactly one of these types and write the doc to match:
- Overview – high-level context (e.g. docs/overview/architecture.md).
- Usage / How-to – step-by-step instructions and workflows (e.g. docs/usage/cli-usage.md).
- Design / Internals – how a subsystem works, constraints, and tradeoffs (e.g. docs/design/design-policy-engine.md).
- Decision (ADR) – a single architectural or product decision per file (e.g. docs/decisions/ADR-0003-policy-language-versioning.md).
- Reference – schemas, config keys, enums, etc. (e.g. docs/overview/data-model.md).
3. Before creating a new doc
- First, search existing docs under /docs for a suitable place to add or extend content.
- Prefer updating an existing doc over creating a new one if:
- The topic clearly matches an existing file’s scope, or
- The new content would naturally be another section in that file.
- Create a new doc only when the topic is clearly distinct and would make an existing doc too long or unfocused.
4. Structure and size
- Each doc must have:
- A short title
- A concise “Purpose” section explaining what the doc covers and who it’s for.
- Clear headings for major sections.
- Keep docs small and focused: they should be easy to ingest in a single LLM context window.
- Avoid duplicating large blocks of content across docs; link instead.
5. Indexing and cross-links
- Every new doc must:
- Be added to /docs/INDEX.md under the appropriate section.
- If applicable, be added to the relevant sub-index (e.g. docs/design/DESIGN_INDEX.md).
- At the bottom of each doc, include a ## Related docs section linking to:
- The relevant index file(s).
- Closely related design/usage/ADR docs (3–5 links is ideal).
6. Consistency for agents
- When updating docs, preserve the existing structure and style of the file.
- Don’t introduce new doc types, directories, or naming conventions without:
- Updating docs/INDEX.md and any relevant index doc, and
- Clearly documenting the new pattern.
- If a doc grows too large or mixes topics, refactor by:
- Splitting into smaller docs under the same folder.
- Updating all relevant indexes and Related docs sections to point to the new structure.

## Recent Changes
- 004-policy-engine: Added Python 3.10+ (per pyproject.toml) + click (CLI), PyYAML (policy parsing), subprocess (mkvpropedit/ffmpeg invocation), sqlite3 (stdlib)
- 001-project-skeleton: Added Python 3.10+ (minimum supported; CI will test 3.10, 3.11, 3.12) + ruff (linting/formatting), pytest (testing)
- 002-library-scanner: Added hybrid Python/Rust architecture with maturin build system, click CLI, MediaIntrospector protocol
