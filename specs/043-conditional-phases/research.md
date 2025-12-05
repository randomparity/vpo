# Research: Conditional Phase Execution

**Feature**: 043-conditional-phases
**Date**: 2025-12-04

## Research Topics

### R1: Existing Phase Infrastructure

**Question**: How does the current V11/V12 phase system track phase state and outcomes?

**Findings**:
- `V11WorkflowProcessor` in `workflow/v11_processor.py` orchestrates phase execution
- `PhaseResult` dataclass tracks per-phase results (success, modified, actions taken)
- `FileProcessingResult` aggregates all phase results for a file
- No explicit "skipped" state exists currently - phases either run or don't (via --phases filter)
- `OnErrorMode` enum already exists with `CONTINUE`, `STOP`, `SKIP` values in `policy/models.py`

**Decision**: Extend `PhaseResult` to include skip reason; add `PhaseOutcome` enum for dependency resolution.

**Rationale**: Reuses existing result infrastructure while adding explicit skip tracking.

**Alternatives Considered**:
1. New result type hierarchy - rejected (unnecessary complexity)
2. Boolean flags on PhaseResult - rejected (less expressive than enum)

---

### R2: Skip Condition Evaluation Context

**Question**: What file metadata is available for skip condition evaluation?

**Findings**:
- `FileInfo` dataclass contains: path, size, duration, container
- `TrackInfo` contains per-track: codec, language, channels, resolution (for video)
- `IntrospectionResult` from ffprobe provides all metadata before processing
- Existing condition evaluation in `policy/conditions.py` already handles similar predicates

**Decision**: Skip conditions evaluate against `FileInfo` + list of `TrackInfo` before phase execution.

**Rationale**: All required metadata is available from introspection; no additional I/O needed.

**Alternatives Considered**:
1. Re-introspect for skip evaluation - rejected (violates NFR-001: no disk I/O)
2. Use cached DB data only - rejected (may be stale)

---

### R3: Circular Dependency Detection Algorithm

**Question**: What's the most efficient way to detect circular dependencies in phase graphs?

**Findings**:
- Kahn's algorithm: O(V+E) using in-degree counting and queue
- DFS with coloring: O(V+E) using white/gray/black node states
- Both detect cycles and can identify the cycle path for error messages
- For 20 phases max, either is effectively instant (< 1ms)

**Decision**: Use DFS with coloring for cycle detection.

**Rationale**:
- DFS naturally tracks the path, making it easy to report which phases form the cycle
- Simpler to implement without external dependencies
- Can be done during policy validation (not at runtime)

**Alternatives Considered**:
1. Kahn's algorithm - equivalent performance, slightly harder to extract cycle path
2. NetworkX library - rejected (new dependency for simple algorithm)

---

### R4: Integration with Existing `--phases` Filter

**Question**: How should dependency validation interact with `--phases` CLI filter?

**Findings**:
- Current `--phases` accepts comma-separated phase names
- Validates names against policy's phases list (rejects unknown names)
- Executes only selected phases in policy-defined order
- No dependency awareness currently

**Decision**: Two-level validation:
1. At policy load: reject circular dependencies (hard error)
2. At `--phases` use: warn if selected phases have dependencies on non-selected phases

**Rationale**:
- Hard errors for broken policies (circular deps)
- Soft warnings for potentially intentional partial runs (user may know what they're doing)
- Allows advanced users to skip phases they've already run manually

**Alternatives Considered**:
1. Hard error for missing dependencies - rejected (too restrictive for power users)
2. Auto-include dependencies - rejected (changes user intent, may run expensive phases unexpectedly)

---

### R5: Per-Phase Error Handling Override

**Question**: How should phase-level `on_error` interact with global `config.on_error`?

**Findings**:
- Global `on_error` in `GlobalConfig` already implemented
- Current flow: phase fails → check global on_error → continue/stop/skip
- Need to insert phase-level check before global fallback

**Decision**: Phase-level `on_error` takes precedence when specified; falls back to global config when not specified.

**Rationale**:
- Most specific wins (standard override pattern)
- Existing policies continue to work (backward compatible)
- Simple logic: `phase.on_error or global_config.on_error`

**Alternatives Considered**:
1. Merge strategies (e.g., "strictest wins") - rejected (confusing semantics)
2. Required at both levels - rejected (verbose, breaks existing policies)

---

### R6: Phase Modification Tracking for `run_if`

**Question**: How to track whether a phase "made changes" for `run_if: { phase_modified: ... }`?

**Findings**:
- `PhaseResult.file_modified` boolean already exists
- Set by executor when any operation modifies the file
- Re-introspection triggered when `file_modified=True`

**Decision**: Use existing `PhaseResult.file_modified` for `run_if: { phase_modified: ... }` evaluation.

**Rationale**: Exact field needed already exists and is reliably set.

**Alternatives Considered**:
1. New tracking mechanism - rejected (duplicates existing functionality)
2. Check file mtime - rejected (unreliable, I/O)

---

### R7: Skip Condition Field Names

**Question**: What field names should be used for skip conditions to match existing patterns?

**Findings**:
- Existing skip_if in transcode uses: `codec_matches`, `resolution_within`, `bitrate_under`
- File-level conditions: `file_size_under`, `file_size_over`, `duration_under`, `duration_over`
- Track existence: `audio_codec_exists`, `subtitle_language_exists`
- Pattern: `{attribute}_{comparison}` or `{track_type}_{attribute}_exists`

**Decision**: Use consistent naming pattern:
- File attributes: `container`, `file_size_under`, `file_size_over`, `duration_under`, `duration_over`, `resolution`, `resolution_under`
- Video: `video_codec`
- Track existence: `audio_codec_exists`, `subtitle_language_exists`

**Rationale**: Follows existing naming conventions; self-documenting field names.

**Alternatives Considered**:
1. Generic predicate syntax (`{ field: video_codec, op: in, value: [hevc] }`) - rejected (verbose, different from existing style)

---

## Summary

All research topics resolved. Key decisions:

| Topic | Decision |
|-------|----------|
| Phase outcome tracking | Extend PhaseResult, add PhaseOutcome enum |
| Skip evaluation context | FileInfo + TrackInfo from introspection |
| Cycle detection | DFS with coloring at policy load time |
| --phases interaction | Warn on missing deps, don't auto-include |
| Error handling override | Phase-level takes precedence over global |
| Modification tracking | Use existing PhaseResult.file_modified |
| Skip condition naming | Follow existing `{attribute}_{comparison}` pattern |
