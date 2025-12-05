# Feature Specification: Conditional Phase Execution

**Feature Branch**: `043-conditional-phases`
**Created**: 2025-12-04
**Status**: Draft
**Input**: User description: "Conditional phase execution, per-phase error handling, and phase dependencies for V12 policy workflows"
**Related**: Extends `specs/037-user-defined-phases/` (items previously marked "Out of Scope")

## Clarifications

### Session 2025-12-04

- Q: When a phase's dependency was skipped (not failed), should the dependent phase still run? → A: Skipped dependency = unmet (dependent phases also skip).

## Overview

This feature extends VPO's V12 phase system with three capabilities that were deferred from the original user-defined phases implementation:

1. **Conditional phase execution**: Skip phases based on file characteristics or previous phase outcomes
2. **Per-phase error handling**: Override global `on_error` behavior at the phase level
3. **Phase dependencies**: Define prerequisites that must be satisfied before a phase runs

These features enable more sophisticated workflows where phases adapt to file characteristics and processing context, reducing unnecessary operations and providing finer-grained control over error recovery.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Skip Expensive Phases When Unnecessary (Priority: P0)

As a media library owner processing thousands of files, I want phases to be skipped automatically when their operations aren't needed, so that I don't waste time and resources on unnecessary processing.

**Why this priority**: This is the core value proposition. Transcoding is expensive (minutes to hours per file). If a file already meets quality targets, skipping the entire transcode phase saves significant time and prevents accidental re-encoding.

**Independent Test**: Create a policy with a conditional transcode phase, process an already-compliant file, verify the phase is skipped with a log message explaining why.

**Acceptance Scenarios**:

1. **Given** a phase with `skip_when: { video_codec: [hevc, h265] }`, **When** processing an HEVC file, **Then** the entire phase is skipped and logs indicate "Phase 'transcode' skipped: video_codec matches [hevc, h265]".
2. **Given** a phase with `skip_when: { audio_codec_exists: truehd }`, **When** processing a file with TrueHD audio, **Then** the phase is skipped.
3. **Given** a phase with `skip_when: { file_size_under: 5GB }`, **When** processing a 3GB file, **Then** the phase is skipped.
4. **Given** a phase with no skip conditions, **When** processing any file, **Then** the phase executes normally.
5. **Given** a phase with `skip_when` that doesn't match, **When** processing a file, **Then** the phase executes normally.

---

### User Story 2 - Per-Phase Error Recovery (Priority: P1)

As a user running batch processing overnight, I want to specify different error handling per phase so that non-critical phases can fail without stopping the entire workflow, while critical phases halt processing immediately.

**Why this priority**: Different phases have different criticality. A failed transcription (analysis) shouldn't stop transcoding, but a failed transcode might mean the file is corrupted and should halt further processing.

**Independent Test**: Create a policy with phases having different `on_error` settings, trigger failures in each, verify each phase responds according to its own setting.

**Acceptance Scenarios**:

1. **Given** a phase with `on_error: continue`, **When** the phase fails, **Then** processing continues to the next phase and the failure is logged.
2. **Given** a phase with `on_error: stop`, **When** the phase fails, **Then** processing halts immediately with a non-zero exit code.
3. **Given** a phase with `on_error: skip`, **When** the phase fails, **Then** the phase is marked as skipped, processing continues, and the failure is logged as a warning.
4. **Given** a phase without `on_error` specified, **When** the phase fails, **Then** the global `config.on_error` setting is used.
5. **Given** global `on_error: stop` and phase `on_error: continue`, **When** the phase fails, **Then** the phase-level setting takes precedence and processing continues.

---

### User Story 3 - Phase Dependencies (Priority: P2)

As a power user building complex workflows, I want to specify that certain phases depend on others so that dependent phases are automatically skipped when their prerequisites didn't run or failed.

**Why this priority**: Enables logical workflow structures where later phases assume earlier phases succeeded. Without this, users must manually track which phases ran and adjust subsequent runs.

**Independent Test**: Create a policy where phase B depends on phase A, skip phase A via `--phases`, verify phase B is also skipped with a dependency message.

**Acceptance Scenarios**:

1. **Given** phase "finalize" with `depends_on: [transcode]`, **When** transcode phase is skipped, **Then** finalize phase is also skipped with log "Phase 'finalize' skipped: dependency 'transcode' did not complete".
2. **Given** phase "finalize" with `depends_on: [transcode]`, **When** transcode phase fails, **Then** finalize phase is skipped (dependency not satisfied).
3. **Given** phase "finalize" with `depends_on: [transcode]`, **When** transcode phase succeeds, **Then** finalize phase executes normally.
4. **Given** phase "cleanup" with `depends_on: [normalize, analyze]`, **When** both dependencies succeed, **Then** cleanup phase executes.
5. **Given** phase "cleanup" with `depends_on: [normalize, analyze]`, **When** normalize succeeds but analyze fails, **Then** cleanup phase is skipped.
6. **Given** `--phases finalize` without including transcode, **When** finalize depends on transcode, **Then** error message indicates missing dependency.

---

### User Story 4 - Conditional Phase Based on Previous Phase Outcome (Priority: P2)

As a user, I want phases to run conditionally based on whether previous phases made changes, so that I can create efficient workflows that skip redundant operations.

**Why this priority**: Enables smart workflows where expensive phases only run when earlier phases actually modified the file. This is an optimization that builds on the dependency system.

**Independent Test**: Create a policy where phase B only runs if phase A made changes, process a file where A makes no changes, verify B is skipped.

**Acceptance Scenarios**:

1. **Given** phase "verify" with `run_if: { phase_modified: normalize }`, **When** normalize phase made changes, **Then** verify phase executes.
2. **Given** phase "verify" with `run_if: { phase_modified: normalize }`, **When** normalize phase made no changes, **Then** verify phase is skipped with log "Phase 'verify' skipped: 'normalize' made no modifications".
3. **Given** phase with both `skip_when` and `run_if`, **When** `skip_when` matches, **Then** phase is skipped regardless of `run_if`.

---

### Edge Cases

- **Circular dependencies**: Policy validation rejects phases with circular dependency chains (e.g., A depends on B, B depends on A).
- **Self-dependency**: Policy validation rejects a phase that depends on itself.
- **Missing dependency target**: If `depends_on` references a non-existent phase name, validation fails with a clear error.
- **All phases skipped**: If all phases are skipped due to conditions, processing completes successfully with a summary indicating no phases executed.
- **skip_when evaluation failure**: If a condition cannot be evaluated (e.g., missing track metadata), the phase executes with a warning logged.
- **Empty depends_on array**: Treated as no dependencies; phase runs normally.
- **Multiple conditions in skip_when**: Conditions are combined with OR logic (any match causes skip).
- **Dependency on skipped phase**: If phase A is skipped (for any reason), phases that depend on A are also skipped. A skipped phase does not satisfy dependency requirements.

## Requirements *(mandatory)*

### Functional Requirements

#### Conditional Execution (skip_when)

- **FR-001**: Phase schema MUST support an optional `skip_when` field containing skip conditions.
- **FR-002**: Skip conditions MUST support file characteristic checks: `video_codec`, `audio_codec_exists`, `subtitle_language_exists`, `container`, `resolution`, `file_size_under`, `file_size_over`, `duration_under`, `duration_over`.
- **FR-003**: When any skip condition matches, the entire phase MUST be skipped without executing any operations.
- **FR-004**: Skipped phases MUST log the reason (which condition matched) at INFO level.
- **FR-005**: Skip condition evaluation MUST occur before phase backup creation (no disk I/O for skipped phases).

#### Per-Phase Error Handling

- **FR-006**: Phase schema MUST support an optional `on_error` field with values: `continue`, `stop`, `skip`.
- **FR-007**: Phase-level `on_error` MUST override global `config.on_error` when specified.
- **FR-008**: `on_error: continue` MUST log the error and proceed to the next phase.
- **FR-009**: `on_error: stop` MUST halt processing immediately with appropriate exit code.
- **FR-010**: `on_error: skip` MUST mark the phase as skipped (not failed), log a warning, and continue.
- **FR-011**: When `on_error` is not specified at phase level, global `config.on_error` MUST be used.

#### Phase Dependencies

- **FR-012**: Phase schema MUST support an optional `depends_on` field containing a list of phase names.
- **FR-013**: A phase with unmet dependencies MUST be skipped with a log message identifying which dependency was not satisfied.
- **FR-014**: A dependency is "met" only when the referenced phase completed successfully; skipped or failed phases do not satisfy dependencies.
- **FR-015**: Policy validation MUST reject circular dependencies with a clear error message.
- **FR-016**: Policy validation MUST reject dependencies on non-existent phase names.
- **FR-017**: When using `--phases` filter, the system MUST warn if selected phases have dependencies on non-selected phases.

#### Conditional Execution (run_if)

- **FR-018**: Phase schema MUST support an optional `run_if` field for positive conditions.
- **FR-019**: `run_if: { phase_modified: <phase-name> }` MUST only run the phase if the referenced phase made file modifications.
- **FR-020**: When both `skip_when` and `run_if` are present, `skip_when` MUST be evaluated first; if it matches, `run_if` is not evaluated.

#### CLI and Output

- **FR-021**: JSON output MUST include skip reasons for each skipped phase.
- **FR-022**: JSON output MUST include dependency resolution status for each phase.
- **FR-023**: Progress output MUST indicate when phases are skipped and why.

### Non-Functional Requirements

- **NFR-001**: Skip condition evaluation MUST complete in < 10ms per phase (no disk I/O).
- **NFR-002**: Dependency resolution MUST complete in < 1ms for policies with up to 20 phases.
- **NFR-003**: Circular dependency detection MUST be performed at policy load time, not runtime.

### Key Entities

- **SkipCondition**: A predicate evaluated against file metadata to determine if a phase should be skipped. Supports various file characteristic checks.
- **PhaseOutcome**: The result of a phase execution: `completed` (success), `failed` (error), `skipped` (condition or dependency not met).
- **DependencyGraph**: Internal representation of phase dependencies for validation and resolution.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can skip transcode phases for already-compliant files, reducing processing time by 90%+ for those files.
- **SC-002**: Batch processing with mixed-criticality phases completes without manual intervention when non-critical phases fail.
- **SC-003**: Policy validation catches circular dependencies before any file processing begins.
- **SC-004**: Skip condition evaluation adds no measurable overhead (< 10ms per file).
- **SC-005**: Users can create 6-phase workflows where 3+ phases have conditional execution without policy complexity becoming unmanageable.
- **SC-006**: Log output clearly indicates why each skipped phase was skipped, enabling users to understand workflow behavior.

## Out of Scope

- Parallel phase execution (phases always run sequentially)
- Phase templates or inheritance
- Dynamic phase ordering based on conditions (order is always as defined in policy)
- Inter-file dependencies (phases only consider current file state)
- Conditional operations within a phase (use existing conditional rules for that)

## Schema Example

```yaml
schema_version: 12

config:
  audio_language_preference: [eng, und]
  on_error: continue  # Global default

phases:
  - name: analyze
    transcription:
      enabled: true
    on_error: skip  # Analysis failure shouldn't stop processing

  - name: normalize
    container:
      target: mkv
    audio_filter:
      languages: [eng, und]
    on_error: stop  # Container issues are critical

  - name: transcode
    skip_when:
      video_codec: [hevc, h265]
      resolution_under: 1080p
    transcode:
      video:
        target_codec: hevc
        quality:
          mode: crf
          crf: 20
    depends_on: [normalize]
    on_error: stop

  - name: verify
    run_if:
      phase_modified: transcode
    conditional:
      - name: check_output_size
        when:
          file_size_over: 10GB
        then:
          - log_warning: "Output file exceeds 10GB"
    depends_on: [transcode]

  - name: cleanup
    attachment_filter:
      remove_all: true
    depends_on: [normalize]
    on_error: continue  # Cleanup failure is non-critical
```

## Assumptions

- The existing V12 schema structure is preserved; new fields are additive.
- `skip_when` conditions use the same file metadata available to existing policy conditions.
- Phase outcomes are tracked internally during processing and available for dependency/run_if evaluation.
- The `--phases` CLI flag continues to work, with dependency warnings added when dependencies are not included.
