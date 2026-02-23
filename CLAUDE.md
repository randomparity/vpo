# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Video Policy Orchestrator (VPO) is a spec-driven tool for scanning, organizing, and transforming video libraries using user-defined policies. The project analyzes media files and applies YAML policies to normalize track ordering, metadata, language tags, and more.

## Build & Test Commands

```bash
# First-time setup (creates venv, installs deps, builds Rust, installs hooks)
make setup                              # Requires uv or pyenv
source .venv/bin/activate               # Activate the virtual environment

# Run tests
uv run pytest                           # All tests
uv run pytest tests/unit/               # Unit tests only
uv run pytest -k test_name              # Single test by name
uv run pytest tests/path/to_file.py    # Single test file
uv run pytest -m "not integration"      # Skip integration tests
uv run pytest --cov=vpo --cov-report=html  # With coverage report

# Linting & formatting
make lint                               # Python + Rust lint
make format                             # Python + Rust format

# Rebuild Rust extension (after modifying Rust code)
uv run maturin develop

# Run CLI
uv run vpo --help
uv run vpo scan /path/to/videos
uv run vpo inspect /path/to/file.mkv
uv run vpo policy run --policy policy.yaml /path/to/file.mkv --dry-run

# Run web UI daemon
uv run vpo serve --port 8080          # Start daemon with web UI

# Check external tool availability
make check-deps                         # Verify ffmpeg, mkvtoolnix installed
uv run vpo doctor                       # Runtime tool check
```

## Tech Stack

- **Python 3.10-3.13** with click (CLI), pydantic, PyYAML, aiohttp (daemon), Jinja2 (templates)
- **Rust** (PyO3/maturin) for parallel file discovery and hashing in `crates/vpo-core/`
- **SQLite** database at `~/.vpo/library.db` (schema version 20)
- **Web UI**: Vanilla JavaScript (ES6+), no frameworks - uses polling for live updates
- **External tools:** ffprobe (introspection), mkvpropedit/mkvmerge (MKV editing), ffmpeg (metadata editing)

## Architecture

```
src/vpo/
├── cli/           # Click commands: scan, inspect, process, doctor, serve, report, db, analyze, policy, plugin, config
├── config/        # Configuration loading and models
├── db/            # SQLite schema, models, and query functions (see below)
├── executor/      # Tool executors: mkvpropedit, mkvmerge, ffmpeg_metadata, transcode
├── introspector/  # MediaIntrospector protocol, ffprobe implementation
├── jobs/          # Background job management, logging, queue operations
├── plugin/        # Plugin system: registry, loader, interfaces, events
├── plugin_sdk/    # SDK helpers for plugin authors
├── plugins/       # Built-in reference plugins
├── policy/        # PolicySchema loading, Plan evaluation, track matchers (see types.py)
├── scanner/       # Orchestrates discovery and introspection
├── server/        # aiohttp daemon: app, routes, lifecycle, signals
│   ├── ui/        # Web UI: Jinja2 templates, routes, models
│   └── static/    # CSS, JavaScript (vanilla JS, no frameworks)
├── tools/         # External tool detection, FFmpeg progress parsing, capability caching
└── workflow/      # V11WorkflowProcessor: multi-phase policy execution pipeline

crates/vpo-core/   # Rust extension for parallel discovery/hashing
```

**Key data flows:**
1. `scan` → discovers files (Rust) → introspects via ffprobe → stores in SQLite
2. `inspect` → reads file from DB or live introspection → displays track info
3. `process` → loads policy YAML → evaluates against file → produces Plan → executes via mkvpropedit/ffmpeg
4. `serve` → starts aiohttp daemon → serves web UI and REST API → manages background jobs

## Jobs Module

The `jobs/` module provides shared utilities for CLI and daemon job processing: progress reporting (`ProgressReporter` protocol with `StderrProgressReporter`, `DatabaseProgressReporter`, `NullProgressReporter` implementations), workflow execution (`WorkflowRunner` with pluggable `JobLifecycle`), job queue operations, and background workers.

## Code Quality

- After editing Python files, always run `ruff check --fix` (or the project's configured linter) before committing. Pay special attention to import ordering (E402, isort) as these are the most common post-edit failures.
- When making multi-file changes, run the full test suite before committing. Do not commit partial batches without confirming tests pass. If tests exceed 5000+, run targeted tests vs. running the full suite.
- When delegating to review agents, always consolidate findings into a single prioritized implementation plan with batched commits. Use TodoWrite to track batch progress.

## Development Guidelines

- Prefer explicit, well-typed dataclasses/models over dicts
- Preserve existing patterns for time handling (UTC), IDs, logging, and config
- No local-time datetime storage, hardcoded paths, ad-hoc subprocess calls, or inline SQL in business logic
- Before finalizing: check idempotence, error handling, logging/auditability, and tests

**Test markers** (defined in pyproject.toml):
- `@pytest.mark.integration` - Tests requiring external tools (ffprobe, mkvtoolnix)
- `@pytest.mark.slow` - Tests that take longer than usual

## Git Commit Guidelines

This project uses pre-commit hooks (ruff format, trailing whitespace, etc.) that may modify files during commit.

**When a commit fails due to pre-commit hooks:**
1. **Stage the reformatted files**: `git add <modified-files>`
2. **Run the same commit command again** (do NOT use `--amend`)
3. The second commit attempt should succeed with all hooks passing

**Never use `git commit --amend`** after a hook failure - this risks amending someone else's commit or a commit that was already pushed. Always create a fresh commit attempt by re-running the original commit command.

**Pre-commit workflow example:**
```bash
# First attempt - hooks may reformat files
git add . && git commit -m "feat: add feature"
# If hooks modified files, the commit fails

# Correct recovery - stage and retry (NO --amend)
git add . && git commit -m "feat: add feature"
# Second attempt succeeds
```

## Constitution

This project has a formal constitution at `.specify/memory/constitution.md` with 18 core principles. Key rules:

- **Datetime**: Always UTC, ISO-8601 format, convert to local only at presentation layer
- **Identity**: Use UUIDv4 for entities, never use file paths as primary keys
- **Paths**: Use `pathlib.Path`, no hardcoded separators, must work on Linux and macOS
- **Schemas**: Versioned with explicit migration logic; bump version on changes
- **Idempotency**: All policy operations must be safe to repeat
- **IO Separation**: Core logic in pure functions; external tools behind adapters
- **Concurrency**: Use `DaemonConnectionPool` for thread-safe DB access; `ThreadPoolExecutor` for parallel CLI operations

## Core Utilities

The `core/` module provides pure utility functions with no external dependencies. Key functions: `normalize_string(s)` (casefold + strip), `compare_strings_ci(a, b)`, `run_command(args, timeout)`.

## Database Module

The `db/` module splits types, queries, operations, and views into separate files. Import from the package (`from vpo.db import FileRecord, get_file_by_path`) or from submodules for internal/test use. `models.py` is a deprecated re-export shim.

**Key types:**
- Domain models: `TrackInfo`, `FileInfo`, `IntrospectionResult`
- Records: `FileRecord`, `TrackRecord`, `Job`, `PlanRecord`
- View models: `FileListViewItem`, `TranscriptionDetailView` (typed alternatives to dict returns)
- Enums: `JobStatus`, `JobType`, `PlanStatus`, `OperationStatus`

**View queries** return typed dataclasses via `_typed` suffix variants (e.g., `get_files_filtered_typed()` returns `list[FileListViewItem]`).

## Import Conventions

- **Public API**: Import from package (`from vpo.db import FileRecord`). Functions/classes in `__all__` are stable interfaces.
- **Private/test use**: Import from defining module (`from vpo.db.queries.helpers import _escape_like_pattern`). Tests import private functions from their defining module, not re-exports.

### Layer Dependencies

```
cli/ server/           # Presentation layer
    ↓
workflow/ scanner/     # Orchestration layer
    ↓
policy/ executor/      # Business logic layer
    ↓
db/ introspector/      # Data access layer
    ↓
core/ tools/           # Utilities (no VPO imports)
```

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

## Web UI Development

The web UI uses server-rendered HTML with JavaScript enhancements:
- **Templates**: Jinja2 templates in `server/ui/templates/`
- **JavaScript**: Vanilla JS modules in `server/static/js/` (no build step, linted with ESLint)
- **CSS**: Plain CSS in `server/static/css/`
- **API**: REST endpoints at `/api/*` return JSON
- **Security**: CSP headers applied to HTML responses (see `SECURITY_HEADERS` in routes.py)

### Policy Editor

The visual policy editor (`/policies/{name}/edit`) provides form-based editing of YAML policy files:
- **Round-trip preservation**: Uses `ruamel.yaml` to preserve unknown fields and comments
- **Concurrency**: Detects concurrent modifications via last_modified timestamps
- **Editor module**: `src/vpo/policy/editor.py` (PolicyRoundTripEditor class)
- **Routes**: GET/PUT `/api/policies/{name}` for load/save, POST `/api/policies/{name}/validate` for dry-run validation
- **Usage docs**: See `/docs/usage/policy-editor.md` for user guide

## Policy Schema

The current policy schema version is **V13** (defined in `policy/loader.py` as `SCHEMA_VERSION`). **Only V13 is supported**—no backward compatibility with older schema versions.

Key V13 features:
- Track filtering (keep_audio, keep_subtitles, filter_attachments), container conversion
- Conditional rules (when/then/else conditions and actions)
- Audio synthesis (create downmixed or re-encoded tracks)
- Video/audio transcoding with skip conditions, quality settings, hardware acceleration
- Multi-language conditions (audio_is_multi_language), set_forced/set_default actions
- skip_if_exists criteria, not_commentary filter
- Workflow configuration (phases, auto_process, on_error)
- Music/sfx/non_speech track type support
- Enhanced conditional rule operators (EXISTS operator)
- Plugin metadata conditions (access plugin-provided metadata in policy conditions)
- **Conditional phases**: skip_when, depends_on, run_if, per-phase on_error override

**Phased format only**: Policies use `PhasedPolicySchema` with multi-phase pipelines (`phases` and `config` sections). Flat policy format is no longer supported.

**Example policy with transcoding:**
```yaml
schema_version: 13
config:
  on_error: skip
phases:
  - name: transcode
    transcode:
      video:
        to: hevc
        skip_if:
          codec_matches: [hevc, h265]
          resolution_within: 1080p
          bitrate_under: 15M
        crf: 20
        preset: medium
        max_resolution: 1080p
        scale_algorithm: lanczos
        hw: auto
        hw_fallback: true
      audio:
        preserve: [truehd, dts-hd, flac]
        to: aac
        bitrate: 192k
```

**Key modules:**
- `policy/types.py`: All schema dataclasses and enums (PolicySchema, PhasedPolicySchema, TrackType, etc.) — V13 field names: `to`, `crf`, `preset`, `max_resolution`, `scale_algorithm`, `hw`, `hw_fallback`, `preserve`, `bitrate`
- `policy/pydantic_models.py`: Pydantic models for YAML parsing and validation
- `policy/conversion.py`: Functions to convert Pydantic models to frozen dataclasses
- `policy/loader.py`: High-level loading functions (load_policy, load_policy_from_dict)
- `executor/transcode.py`: TranscodeExecutor, FFmpeg command building, edge case detection
- `policy/transcode.py`: Audio plan creation for audio config
- `workflow/skip_conditions.py`: Phase skip condition evaluation (evaluate_skip_when)

**Conditional Phase Execution:**

Phased policies support conditional execution through four mechanisms:

1. **skip_when**: Skip phase based on file characteristics. Requires a `mode` field (`any` = OR logic, skip if any condition matches; `all` = AND logic, skip only if all match)
   - `mode: any` or `mode: all` - required, controls matching logic
   - `video_codec: [hevc, h265]` - skip if video codec matches
   - `file_size_under: 1GB` - skip if file under threshold
   - `resolution_under: 1080p` - skip if resolution below
   - `duration_under: 30m` - skip if duration under
   - `audio_codec_exists: truehd` - skip if audio codec present
   - `container: [mkv]` - skip if container matches

2. **depends_on**: Skip phase if dependencies didn't complete
   - List of phase names that must COMPLETE before this phase runs
   - If any dependency failed or was skipped, this phase is skipped

3. **run_if**: Run phase only if condition met
   - `phase_modified: transcode` - run only if named phase modified file

4. **on_error**: Per-phase error handling override
   - `skip` - skip remaining phases for this file
   - `continue` - log and continue to next phase
   - `fail` - stop batch processing

**Example phased policy with conditionals:**
```yaml
schema_version: 13
phases:
  - name: normalize
    container:
      target: mkv

  - name: transcode
    skip_when:
      mode: any
      video_codec: [hevc, h265]
    transcode:
      video:
        to: hevc

  - name: verify
    run_if:
      phase_modified: transcode
    depends_on: [transcode]
    rules:
      match: first
      items:
        - name: check
          when: { exists: { track_type: video } }
          then: [{ warn: "Transcode complete" }]
```

**Transcode edge cases:**
- VFR detection: warns about variable frame rate content
- Bitrate estimation: estimates from file size when metadata missing
- Multiple video streams: selects primary, warns about others
- HDR preservation: warns when scaling HDR content
- HW encoder fallback: falls back to CPU if hardware unavailable

## Plugin System

Plugins extend VPO's functionality through a well-defined protocol system:

**Plugin types:**
- `AnalyzerPlugin`: Read-only plugins that enrich metadata (subscribe to `file.scanned`)
- `MutatorPlugin`: Plugins that can modify files (subscribe to `plan.before_execute`, etc.)

**Built-in plugins** in `plugins/`: `radarr_metadata`, `sonarr_metadata` (metadata enrichment from external services), `policy_engine` (core executor), `whisper_transcriber` (speech-to-text). See each plugin's `README.md` for configuration and usage.

**Plugin configuration** goes in `~/.vpo/config.toml` under `[plugins.metadata.<name>]` sections for metadata plugins, `[plugins.<name>]` for others. The current plugin API version is **1.1.0**.

## Condition Evaluation Pattern

When adding new condition types to the policy system:
1. Create condition dataclass in `policy/types.py` (add to `Condition` union type)
2. Add Pydantic model in `policy/pydantic_models.py` for YAML parsing
3. Add parsing case to `_convert_condition()` in `policy/conversion.py`
4. Add evaluation function in `policy/conditions.py`
5. Thread any new context through `policy/evaluator.py`

## Processing Statistics

VPO captures per-file processing statistics across three database tables (`processing_stats`, `action_results`, `performance_metrics`). Key modules: `workflow/stats_capture.py` (`StatsCollector`), `db/views.py` (aggregate queries), `cli/report.py` (CLI via `vpo report`), and `server/ui/routes.py` (REST API at `/api/stats/*`). Use `vpo report --help` for available subcommands.

## Active Technologies
- Python 3.10-3.13 + click (CLI), tarfile (stdlib), json (stdlib), shutil (stdlib) (045-library-backup)
- SQLite database at `~/.vpo/library.db`, backups at `~/.vpo/backups/` (045-library-backup)

## Recent Changes
- 045-library-backup: Added Python 3.10-3.13 + click (CLI), tarfile (stdlib), json (stdlib), shutil (stdlib)
