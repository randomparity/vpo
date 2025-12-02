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

# Run web UI daemon
uv run vpo serve --port 8080          # Start daemon with web UI
```

## Tech Stack

- **Python 3.10+** with click (CLI), pydantic, PyYAML, aiohttp (daemon), Jinja2 (templates)
- **Rust** (PyO3/maturin) for parallel file discovery and hashing in `crates/vpo-core/`
- **SQLite** database at `~/.vpo/library.db` (schema version 17)
- **Web UI**: Vanilla JavaScript (ES6+), no frameworks - uses polling for live updates
- **External tools:** ffprobe (introspection), mkvpropedit/mkvmerge (MKV editing), ffmpeg (metadata editing)

## Architecture

```
src/video_policy_orchestrator/
├── cli/           # Click commands: scan, inspect, apply, doctor, serve, process
├── config/        # Configuration loading and models
├── db/            # SQLite schema, models, and query functions (see below)
├── executor/      # Tool executors: mkvpropedit, mkvmerge, ffmpeg_metadata, transcode
├── introspector/  # MediaIntrospector protocol, ffprobe implementation
├── jobs/          # Background job management, logging, queue operations
├── plugin/        # Plugin system: registry, loader, interfaces, events
├── plugin_sdk/    # SDK helpers for plugin authors
├── plugins/       # Built-in reference plugins
├── policy/        # PolicySchema loading, Plan evaluation, track matchers
├── scanner/       # Orchestrates discovery and introspection
├── server/        # aiohttp daemon: app, routes, lifecycle, signals
│   ├── ui/        # Web UI: Jinja2 templates, routes, models
│   └── static/    # CSS, JavaScript (vanilla JS, no frameworks)
├── tools/         # External tool detection and capability caching
└── workflow/      # V11WorkflowProcessor: multi-phase policy execution pipeline

crates/vpo-core/   # Rust extension for parallel discovery/hashing
```

**Key data flows:**
1. `scan` → discovers files (Rust) → introspects via ffprobe → stores in SQLite
2. `inspect` → reads file from DB or live introspection → displays track info
3. `apply` → loads policy YAML → evaluates against file → produces Plan → executes via mkvpropedit/ffmpeg
4. `serve` → starts aiohttp daemon → serves web UI and REST API → manages background jobs

## Development Guidelines

- Prefer explicit, well-typed dataclasses/models over dicts
- Preserve existing patterns for time handling (UTC), IDs, logging, and config
- No local-time datetime storage, hardcoded paths, ad-hoc subprocess calls, or inline SQL in business logic
- Before finalizing: check idempotence, error handling, logging/auditability, and tests

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
- **Concurrency**: Use `DaemonConnectionPool` for thread-safe DB access via `asyncio.to_thread`

## Database Module Structure

The `db/` module is organized into separate files for types, queries, and views:

```
db/
├── __init__.py   # Public API - re-exports all types and functions
├── types.py      # Enums, dataclasses (records, domain models, view models)
├── queries.py    # CRUD operations (insert, upsert, get, delete)
├── views.py      # Aggregated view queries for UI (library list, transcriptions)
├── schema.py     # Schema creation and migrations
└── models.py     # Backward-compat shim (deprecated, re-exports from above)
```

**Import patterns** (all equivalent):
```python
# Preferred: import from package
from video_policy_orchestrator.db import FileRecord, get_file_by_path

# Or from specific submodule
from video_policy_orchestrator.db.types import FileRecord
from video_policy_orchestrator.db.queries import get_file_by_path

# Legacy (still works, but deprecated)
from video_policy_orchestrator.db.models import FileRecord, get_file_by_path
```

**Key types:**
- Domain models: `TrackInfo`, `FileInfo`, `IntrospectionResult`
- Records: `FileRecord`, `TrackRecord`, `Job`, `PlanRecord`
- View models: `FileListViewItem`, `TranscriptionDetailView` (typed alternatives to dict returns)
- Enums: `JobStatus`, `JobType`, `PlanStatus`, `OperationStatus`

**View queries** return typed dataclasses via `_typed` suffix variants:
- `get_files_filtered()` returns `list[dict]`
- `get_files_filtered_typed()` returns `list[FileListViewItem]`

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
- **JavaScript**: Vanilla JS modules in `server/static/js/` (no build step)
- **CSS**: Plain CSS in `server/static/css/`
- **API**: REST endpoints at `/api/*` return JSON
- **Security**: CSP headers applied to HTML responses (see `SECURITY_HEADERS` in routes.py)

### Policy Editor

The visual policy editor (`/policies/{name}/edit`) provides form-based editing of YAML policy files:
- **Round-trip preservation**: Uses `ruamel.yaml` to preserve unknown fields and comments
- **Concurrency**: Detects concurrent modifications via last_modified timestamps
- **Editor module**: `src/video_policy_orchestrator/policy/editor.py` (PolicyRoundTripEditor class)
- **Routes**: GET/PUT `/api/policies/{name}` for load/save, POST `/api/policies/{name}/validate` for dry-run validation
- **Usage docs**: See `/docs/usage/policy-editor.md` for user guide

## Policy Schema

The current policy schema version is **V12** (defined in `policy/loader.py` as `SCHEMA_VERSION`). **Only V12 is supported**—no backward compatibility with older schema versions.

Key V12 features:
- Track filtering (audio_filter, subtitle_filter, attachment_filter), container conversion
- Conditional rules (when/then/else conditions and actions)
- Audio synthesis (create downmixed or re-encoded tracks)
- Video/audio transcoding with skip conditions, quality settings, hardware acceleration
- Multi-language conditions (audio_is_multi_language), set_forced/set_default actions
- skip_if_exists criteria, not_commentary filter
- Workflow configuration (phases, auto_process, on_error)
- Music/sfx/non_speech track type support
- Enhanced conditional rule operators (EXISTS operator)
- Plugin metadata conditions (access plugin-provided metadata in policy conditions)

**Two policy formats:**
- **Flat format** (`PolicySchema`): Traditional single-section policy
- **Phased format** (`PhasedPolicySchema`): Multi-phase pipelines with `phases` and `config` sections

**Example policy with transcoding:**
```yaml
schema_version: 12
transcode:
  video:
    target_codec: hevc
    skip_if:
      codec_matches: [hevc, h265]
      resolution_within: 1080p
      bitrate_under: 15M
    quality:
      mode: crf
      crf: 20
      preset: medium
    scaling:
      max_resolution: 1080p
      algorithm: lanczos
    hardware_acceleration:
      enabled: auto
      fallback_to_cpu: true
  audio:
    preserve_codecs: [truehd, dts-hd, flac]
    transcode_to: aac
    transcode_bitrate: 192k
```

**Key modules:**
- `policy/models.py`: All schema dataclasses (PolicySchema, PhasedPolicySchema, SkipCondition, QualitySettings, ConditionalRule, etc.)
- `policy/loader.py`: PolicyModel validation, schema loading, SCHEMA_VERSION constant
- `executor/transcode.py`: TranscodeExecutor, FFmpeg command building, edge case detection
- `policy/transcode.py`: Audio plan creation for audio config

**Transcode edge cases:**
- VFR detection: warns about variable frame rate content
- Bitrate estimation: estimates from file size when metadata missing
- Multiple video streams: selects primary, warns about others
- HDR preservation: warns when scaling HDR content
- HW encoder fallback: falls back to CPU if hardware unavailable

## Plugin System

Plugins extend VPO's functionality through a well-defined protocol system:

```
plugin/
├── interfaces.py    # AnalyzerPlugin, MutatorPlugin protocols
├── events.py        # Event types: file.scanned, policy.before_evaluate, etc.
├── registry.py      # PluginRegistry for loading/managing plugins
├── loader.py        # Discovery from entry points and ~/.vpo/plugins/
└── manifest.py      # PluginManifest metadata (name, version, events)

plugins/             # Built-in reference plugins
├── policy_engine/   # Core policy executor (built-in)
└── whisper_transcriber/  # Example analyzer plugin
```

**Plugin types:**
- `AnalyzerPlugin`: Read-only plugins that enrich metadata (subscribe to `file.scanned`)
- `MutatorPlugin`: Plugins that can modify files (subscribe to `plan.before_execute`, etc.)

**Creating a plugin:**
```python
class MyPlugin:
    name = "my-plugin"      # kebab-case identifier
    version = "1.0.0"       # semver
    events = ["file.scanned"]

    def on_file_scanned(self, event: FileScannedEvent) -> dict[str, Any] | None:
        # Return dict to merge into file metadata, or None
        return {"enriched_field": value}
```

**Plugin configuration** goes in `~/.vpo/config.toml` under `[plugins.<name>]` sections.

## Condition Evaluation Pattern

When adding new condition types to the policy system:
1. Create condition dataclass in `policy/models.py` (add to `Condition` union type)
2. Add Pydantic model in `policy/loader.py` for YAML parsing
3. Add parsing case to `convert_condition()` in `policy/loader.py`
4. Add evaluation function in `policy/conditions.py`
5. Thread any new context through `policy/evaluator.py`

## Processing Statistics

VPO captures detailed processing statistics for each file operation:

**Database tables:**
- `processing_stats`: Core metrics (sizes, track counts, transcode info, timing)
- `action_results`: Individual action details (track type, before/after state)
- `performance_metrics`: Per-phase timing data

**Key modules:**
- `workflow/stats_capture.py`: `StatsCollector` class for capturing metrics during workflow execution
- `db/views.py`: View queries (`get_stats_summary()`, `get_recent_stats()`, `get_policy_stats()`)
- `db/types.py`: `ProcessingStatsRecord`, `ActionResultRecord`, `PerformanceMetricsRecord`
- `cli/stats.py`: CLI commands (`vpo stats summary`, `vpo stats recent`, `vpo stats purge`)
- `server/ui/routes.py`: REST API endpoints (`/api/stats/*`)

**CLI Commands:**
```bash
# View summary statistics
vpo stats summary --since 7d

# View recent processing history
vpo stats recent --limit 20

# View per-policy breakdown
vpo stats policies --since 30d

# View single file history
vpo stats file 123

# View single record details
vpo stats detail <stats-id>

# Delete old statistics (purge)
vpo stats purge --before 90d --dry-run   # Preview
vpo stats purge --before 90d             # Execute
vpo stats purge --policy my-policy.yaml  # By policy
vpo stats purge --all --yes              # Delete all
```

**REST API Endpoints:**
- `GET /api/stats/summary` - Aggregate statistics
- `GET /api/stats/recent` - Recent processing history
- `GET /api/stats/policies` - Per-policy breakdown
- `GET /api/stats/policies/{name}` - Single policy stats
- `GET /api/stats/files/{file_id}` - File processing history
- `GET /api/stats/{stats_id}` - Single record detail
- `DELETE /api/stats/purge?before=30d&dry_run=true` - Delete statistics
