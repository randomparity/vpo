# Research: User-Defined Processing Phases

**Feature**: 037-user-defined-phases
**Date**: 2025-11-30

## Research Topics

### R1: Current Workflow Architecture

**Question**: How does the existing V9 workflow system work?

**Findings**:
- `ProcessingPhase` enum defines 3 phases: ANALYZE, APPLY, TRANSCODE
- `WorkflowConfig` dataclass holds phase list, auto_process flag, on_error mode
- `WorkflowProcessor` orchestrates phases via `_init_phases()` dictionary
- Each phase has a dedicated class in `workflow/phases/` (AnalyzePhase, ApplyPhase, TranscodePhase)
- Phases execute sequentially via `process_file()` method

**Decision**: Replace enum-based phase dispatch with dynamic name-based dispatch. Phase classes become operation handlers, not fixed workflow steps.

**Rationale**: User-defined phase names cannot be enumerated at compile time. The operation types (transcode, filter, etc.) are fixed; only the grouping into phases is user-defined.

**Alternatives Considered**:
1. Extend enum with plugin registry - rejected (overengineered for string-based names)
2. Keep three phases, add "custom operations" within APPLY - rejected (doesn't meet spec requirements)

---

### R2: Operation Execution Order Within Phase

**Question**: When a phase contains multiple operations, what order should they execute?

**Findings**:
- Current APPLY phase has implicit ordering: filters → track_order → default_flags → conditional
- Transcode operations have prerequisites (filters must complete first)
- Container conversion may need to happen before or after other operations
- Audio synthesis creates new tracks that subsequent operations may reference

**Decision**: Define canonical operation order within each phase:
1. container (format conversion)
2. audio_filter, subtitle_filter, attachment_filter (track removal)
3. track_order (reordering)
4. default_flags (flag changes)
5. conditional (conditional actions)
6. audio_synthesis (track creation)
7. transcode (codec conversion)
8. transcription (analysis)

**Rationale**: This order ensures:
- Filters run before track_order (can't order removed tracks)
- Synthesis runs before transcode (new tracks available for skip_if_exists)
- Transcription runs last (analyzes final track state)

**Alternatives Considered**:
1. User-specified operation order within phase - rejected (error-prone, complex validation)
2. Dependency-based ordering - rejected (implicit dependencies hard to validate)

---

### R3: Rollback Implementation Strategy

**Question**: How to implement atomic rollback when a phase fails mid-execution?

**Findings**:
- Existing backup system: `backup_path = path.with_suffix('.vpo.bak')`
- `ExecutorResult` includes `backup_path` for restoration
- `restore_from_backup()` function exists in executor module
- Current system backs up before each executor, not per-phase

**Decision**: Phase-level backup strategy:
1. Before phase starts: create backup of current file state
2. Execute all operations in phase (each may create intermediate backups)
3. On success: cleanup phase backup, keep file
4. On failure: restore phase backup, cleanup intermediate states

**Rationale**: Single backup per phase is simpler and sufficient. Intermediate executor backups can be ephemeral (auto-cleanup on phase commit).

**Alternatives Considered**:
1. No rollback (document partial state) - rejected (spec requires rollback)
2. Copy-on-write with atomic rename - rejected (doubles disk usage for large files)

---

### R4: V11 Schema Structure

**Question**: What should the V11 policy schema look like?

**Findings**:
- Current V10 schema has flat structure with workflow.phases as enum list
- Spec example shows phases array with name + operations per entry
- Global config needed for shared settings across phases
- Reserved phase names needed to avoid conflicts

**Decision**: V11 schema structure:
```yaml
schema_version: 11

config:                    # Global configuration
  audio_language_preference: [eng, und]
  on_error: continue
  # ... other shared settings

phases:                    # Ordered list of named phases
  - name: phase-name       # User-defined, alphanumeric + hyphen + underscore
    container: {...}       # Optional: operation configs
    audio_filter: {...}
    transcode: {...}
```

**Rationale**:
- `config` section centralizes shared settings
- `phases` array preserves order (Python dicts are ordered but YAML semantics vary)
- Each phase is a dict with `name` key plus operation keys

**Alternatives Considered**:
1. Keep workflow section with nested phases - rejected (more nesting, less intuitive)
2. Phases as dict keys instead of array - rejected (order not guaranteed in all parsers)

---

### R5: Phase Name Validation

**Question**: What phase names should be allowed/rejected?

**Findings**:
- Spec requires: alphanumeric, hyphens, underscores
- Need to reject reserved words that conflict with schema keys
- Should reject empty names and whitespace-only

**Decision**: Phase name validation rules:
- Pattern: `^[a-zA-Z][a-zA-Z0-9_-]*$` (must start with letter)
- Max length: 64 characters
- Reserved words: `config`, `schema_version`, `phases`
- Uniqueness: no duplicate names within policy

**Rationale**: Starting with letter prevents confusion with YAML special values. Reserved words prevent key collisions. Length limit prevents abuse.

**Alternatives Considered**:
1. Allow numbers first - rejected (could conflict with YAML numeric parsing)
2. No reserved words - rejected (config/schema_version collision would break parsing)

---

### R6: Re-introspection Between Phases

**Question**: When should the system re-introspect files between phases?

**Findings**:
- Spec requires re-introspection after phases that modify files
- FFprobe introspection takes ~200ms per file
- Unnecessary re-introspection wastes time
- Track synthesis and transcode definitely modify files
- Filter operations may remove tracks
- Container conversion may change stream mapping

**Decision**: Track "file modified" flag per phase:
- Operations that modify files set a flag
- After phase completes successfully, if flag is set, re-introspect
- Pass fresh `FileInfo` to next phase

Modifying operations:
- container (always)
- audio_filter, subtitle_filter, attachment_filter (if tracks removed)
- audio_synthesis (always)
- transcode (always)

Non-modifying operations:
- track_order (metadata only, if using mkvpropedit)
- default_flags (metadata only)
- conditional (depends on actions taken)
- transcription (read-only analysis)

**Rationale**: Only re-introspect when necessary. Track-level changes may not require full re-introspection in future optimization.

**Alternatives Considered**:
1. Always re-introspect - rejected (wastes 200ms × phases)
2. Never re-introspect - rejected (stale data causes incorrect skip_if_exists)

---

### R7: CLI --phases Filter Behavior

**Question**: How should the `--phases` CLI flag work with user-defined phase names?

**Findings**:
- Current `--phases` accepts enum values (analyze, apply, transcode)
- User-defined names are arbitrary strings
- Need to handle invalid names gracefully
- May want to run subset of phases in order

**Decision**: `--phases` accepts comma-separated phase names:
- Names validated against policy's phases list
- Unknown names cause immediate error (before processing starts)
- Phases execute in policy-defined order (even if specified out-of-order on CLI)
- Example: `--phases transcode,normalize` runs normalize first (per policy order)

**Rationale**: Respecting policy order prevents broken dependencies. Early validation prevents wasted work on invalid phase names.

**Alternatives Considered**:
1. Execute in CLI-specified order - rejected (could break dependencies)
2. Wildcard/glob patterns - rejected (overengineered for typical use)

---

## Summary

All research topics resolved. Key decisions:

| Topic | Decision |
|-------|----------|
| Phase dispatch | String-based names, dynamic lookup |
| Operation order | Fixed canonical order within phase |
| Rollback | Phase-level backup/restore |
| Schema | V11 with `config` + `phases` array |
| Phase names | Letter-first, 64 char max, reserved words |
| Re-introspection | Track modified flag per phase |
| CLI filter | Comma-separated, policy order respected |
