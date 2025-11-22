<!--
SYNC IMPACT REPORT
==================
Version change: 0.0.0 → 1.0.0 (MAJOR - initial constitution adoption)

Modified principles: N/A (initial version)

Added sections:
- 18 Core Principles (I-XVIII)
- Security & Privacy section
- Development Workflow section
- Governance section with amendment procedures

Removed sections: N/A (initial version)

Templates requiring updates:
- .specify/templates/plan-template.md: ✅ No changes needed (Constitution Check placeholder compatible)
- .specify/templates/spec-template.md: ✅ No changes needed
- .specify/templates/tasks-template.md: ✅ No changes needed
- .specify/templates/agent-file-template.md: ✅ No changes needed
- .specify/templates/checklist-template.md: ✅ No changes needed

Follow-up TODOs: None
-->

# Video Policy Orchestrator Constitution

## Core Principles

### I. Datetime Integrity

All datetime values MUST be stored as timezone-aware UTC. Convert to local time
only at the presentation layer. Use ISO-8601 format (e.g., `2025-01-15T14:30:00Z`)
for all serialized timestamps. Never persist naive or local-time datetimes.

**Rationale**: Eliminates timezone ambiguity in distributed systems and ensures
consistent behavior across geographic regions.

### II. Stable Identity

Every media item, track, and policy MUST have a stable, canonical ID (prefer
UUIDv4 or a content hash). Do not use filenames or paths as primary keys. Treat
filenames/paths as attributes that may change over time.

**Rationale**: Files are frequently renamed, moved, or reorganized. Identity
must persist across these operations to maintain history and relationships.

### III. Portable Paths

Use `pathlib.Path` for all filesystem operations. Assume UTF-8 encoding for file
and metadata text. Never hardcode OS-specific path separators. Code MUST run on
Linux and macOS without modification.

**Rationale**: VPO targets multiple platforms; platform-specific code creates
maintenance burden and user friction.

### IV. Versioned Schemas

All media and policy metadata MUST conform to a documented, versioned schema.
When changing the schema, bump a schema version and provide explicit migration
logic. Avoid free-form dicts; use typed models (Pydantic/dataclasses) and enums
for known categories (codec, language, track type).

**Rationale**: Type safety catches errors at development time. Schema versioning
enables safe evolution without data loss.

### V. Idempotent Operations

All policy application operations MUST be idempotent and deterministic. Running
the same policy twice over the same input MUST NOT introduce duplicates, data
loss, or diverging state. If side effects occur, they MUST be safe to repeat.

**Rationale**: Users re-run scans and policies frequently. Idempotency prevents
accidental corruption and enables safe retry after failures.

### VI. IO Separation

Separate core policy logic from IO/tooling. The core MUST operate on in-memory
models and pure functions. Any interaction with external tools (ffmpeg, mkvmerge,
etc.) MUST be encapsulated behind explicit adapter modules with narrow,
well-typed interfaces.

**Rationale**: Pure functions are testable and predictable. Adapters can be
mocked for testing and swapped for different tools.

### VII. Explicit Error Handling

Handle errors explicitly. For each operation, decide whether errors should:
(a) fail fast, (b) be retried, or (c) be logged and skipped. Use clear, custom
exception types for expected problems (e.g., `InvalidMetadataError`,
`UnsupportedCodecError`) and never silently swallow exceptions.

**Rationale**: Silent failures corrupt data and waste debugging time. Explicit
handling makes error behavior predictable and documented.

### VIII. Structured Logging

Implement structured logging for all batch operations and policy applications.
Every log entry MUST include media ID, policy ID, and operation type. Log both
decisions (e.g., "selected audio track X as primary") and side effects ("rewrote
container with tracks [1,3,2]"). Avoid print-style debugging; use a centralized
logger.

**Rationale**: Structured logs enable automated analysis, debugging, and
auditing of policy decisions across large libraries.

### IX. Configuration as Data

Keep environment-specific details (paths, credentials, hostnames) and
user-defined policies in configuration, not code. The codebase MUST treat
configuration as data, loaded and validated at startup. Avoid embedding absolute
paths or secrets in source files.

**Rationale**: Configuration-as-data enables deployment flexibility and prevents
accidental credential exposure in version control.

### X. Policy Stability

Treat the policy definition format as a public interface. Any change to the
policy schema MUST be backward compatible or accompanied by an explicit migration
path. Document and version the policy schema and avoid breaking existing
policies silently.

**Rationale**: Users invest time crafting policies. Breaking changes without
migration paths destroy user trust and create support burden.

### XI. Plugin Isolation

Define clear plugin interfaces (e.g., `PolicyPlugin`, `MetadataEnricher`) as
abstract base classes or protocols. Plugins MUST depend only on these interfaces
and public data models, not on internal helper modules or private attributes.
Breaking plugin interfaces requires a documented version bump.

**Rationale**: Plugin authors need stable contracts. Internal changes should
not cascade to plugin breakage.

### XII. Safe Concurrency

Any parallel or concurrent processing MUST be explicit and safe. Clearly document
whether threads, processes, or async IO are used. Do not share mutable global
state across workers. For shared resources (database, cache directories), ensure
operations are atomic or protected by appropriate locking/transactions.

**Rationale**: Implicit concurrency causes race conditions. Explicit design
makes parallel code reviewable and debuggable.

### XIII. Database Design

Design the database schema with normalization and queryability in mind. Use
foreign keys, unique constraints, and indexes for media, tracks, and policy
applications. Encapsulate DB access in repository/DAO modules; business logic
MUST NOT embed raw SQL arbitrarily.

**Rationale**: Well-designed schemas prevent data anomalies. DAO encapsulation
enables testing and potential backend changes.

### XIV. Test Media Corpus

Build and maintain a small corpus of test media files with known, documented
metadata and expected outcomes. Use these as fixtures in unit and integration
tests. When a bug is found and fixed, add a regression test based on a minimal
reproduction input.

**Rationale**: Media processing bugs often involve specific codec/container
combinations. Real fixtures catch regressions that synthetic tests miss.

### XV. Stable CLI/API Contracts

CLI commands and programmatic APIs MUST be treated as stable contracts. Reuse
option names and flags consistently (`--input`, `--output`, `--dry-run`,
`--policy`). Any breaking change to the CLI or API MUST be versioned and
documented, not silently altered.

**Rationale**: Users build scripts and automation around CLI flags. Silent
changes break workflows and erode trust.

### XVI. Dry-Run Default

All operations that modify media containers or move files MUST support a
dry-run/preview mode that logs intended actions without applying them. Default
CLI behavior SHOULD be non-destructive where possible (e.g., write to a new file
unless `--in-place` is explicitly requested).

**Rationale**: Destructive defaults cause data loss. Preview-first design gives
users confidence to experiment safely.

### XVII. Data Privacy

Treat all media and metadata as potentially sensitive. No data may be sent to
external services (including LLMs or transcription APIs) unless explicitly
configured by the user. All such integrations MUST be behind clearly named
configuration flags, and logs MUST never contain raw media content.

**Rationale**: Media libraries may contain personal or copyrighted content.
Privacy-by-default protects users from unintended exposure.

### XVIII. Living Documentation

Maintain concise, up-to-date documentation:
1. An architecture overview
2. A "How to add a new policy" guide
3. A "How to debug a failed run" guide

When making non-trivial design changes, update the docs in the same change set
as the code.

**Rationale**: Stale documentation misleads contributors and users. Co-located
updates ensure docs track reality.

## Security & Privacy

- All external service integrations MUST be opt-in via explicit configuration
- Credentials and API keys MUST be loaded from environment or secure config
- Logs MUST NOT contain raw media content, file contents, or user credentials
- Network requests MUST be logged (destination, not payload) for auditability
- Default behavior MUST assume offline operation

## Development Workflow

### Code Review Requirements

- All changes MUST pass CI (lint, type-check, test)
- Schema changes MUST include migration logic and version bump
- Plugin interface changes MUST document breaking changes
- CLI changes MUST update help text and relevant documentation

### Testing Gates

- Unit tests for all pure functions and data transformations
- Integration tests for adapter modules (ffmpeg, mkvmerge wrappers)
- Contract tests for plugin interfaces
- Regression tests for all fixed bugs

### Quality Standards

- Type hints required for all public interfaces
- Docstrings required for public modules and non-trivial functions
- No `# type: ignore` without explanatory comment
- Prefer explicit over implicit in all API design

## Governance

This constitution supersedes all other development practices for the Video
Policy Orchestrator project. Amendments require:

1. **Proposal**: Document the change and rationale in an issue or PR
2. **Review**: At least one maintainer review for MINOR/PATCH changes
3. **Migration Plan**: For breaking changes, document impact and migration path
4. **Version Bump**: Update constitution version per semantic versioning:
   - MAJOR: Principle removal or incompatible redefinition
   - MINOR: New principle or material expansion
   - PATCH: Clarification, wording, or typo fix

All PRs and code reviews SHOULD verify compliance with these principles.
Violations MUST be justified in the PR description with reference to specific
tradeoffs.

Use `CLAUDE.md` for runtime development guidance that may change more frequently.

**Version**: 1.0.0 | **Ratified**: 2025-01-22 | **Last Amended**: 2025-01-22
