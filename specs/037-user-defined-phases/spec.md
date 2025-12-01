# Feature Specification: User-Defined Processing Phases

**Feature Branch**: `037-user-defined-phases`
**Created**: 2025-11-30
**Status**: Draft
**Input**: User description: "Replace the hardcoded workflow phase system (ANALYZE, APPLY, TRANSCODE) with user-defined phases. Users define phases by name and specify which operations run in each phase. Phases execute in the order defined in the policy file."

## Clarifications

### Session 2025-11-30

- Q: What happens when a failure occurs mid-phase after some operations have already modified the file? → A: Rollback - revert all operations in the failed phase to restore file to pre-phase state.

## Overview

This feature replaces VPO's hardcoded three-phase workflow system (ANALYZE, APPLY, TRANSCODE) with a flexible, user-defined phase system. Users define named phases in their policy files and specify which operations run in each phase. This enables single-command processing of complex media normalization workflows without requiring users to understand internal phase mechanics or invoke multiple commands.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Single Command Media Normalization (Priority: P0)

As a media library owner, I want to run a single command that performs all my normalization operations (container conversion, track filtering, audio synthesis, transcoding) so that I don't need to understand the internal phase system or invoke multiple commands.

**Why this priority**: This is the core value proposition of the feature. Without this, users must manually orchestrate multiple command invocations with different flags, which is error-prone and defeats the purpose of a policy-driven workflow.

**Independent Test**: Can be fully tested by creating a policy with multiple phases and running `vpo process -p policy.yaml /path/to/video.mkv`, then verifying all operations executed in order and the output file reflects all transformations.

**Acceptance Scenarios**:

1. **Given** a policy with multiple phases (normalize, synthesize, transcode), **When** I run `vpo process -p policy.yaml /videos`, **Then** all phases execute in order without requiring additional flags.
2. **Given** a policy with transcode operations, **When** I run `vpo process`, **Then** transcoding happens automatically (no `--phases` flag needed).
3. **Given** a policy with audio synthesis before transcoding, **When** processing a file, **Then** the synthesized audio track exists before the transcode phase evaluates skip conditions.
4. **Given** a policy with six phases, **When** processing completes, **Then** logs show each phase name and its operations as they execute.

---

### User Story 2 - Custom Phase Names (Priority: P1)

As a power user, I want to name my phases descriptively (e.g., "cleanup", "enhance", "compress") so that my policies are self-documenting and meaningful to my workflow.

**Why this priority**: Custom naming makes policies readable and maintainable. While the system could work with generic names like "phase1", meaningful names significantly improve user experience and policy comprehension.

**Independent Test**: Can be tested by creating a policy with custom-named phases and verifying the names appear in logs and error messages.

**Acceptance Scenarios**:

1. **Given** a phase named "initial-cleanup", **When** the policy is loaded, **Then** the system accepts the custom name without error.
2. **Given** multiple phases with custom names, **When** processing completes, **Then** logs and output display the custom phase names.
3. **Given** a phase name with invalid characters (e.g., "my phase!"), **When** loading the policy, **Then** the system reports a validation error specifying the invalid characters.
4. **Given** a phase name using allowed characters (alphanumeric, hyphens, underscores), **When** loading the policy, **Then** validation passes.

---

### User Story 3 - Operation Flexibility (Priority: P1)

As a user, I want to put any operation in any phase so that I can control exactly when each operation runs relative to others.

**Why this priority**: This flexibility is essential for complex workflows where operation order matters (e.g., creating synthesized audio before transcoding so the transcode phase can reference it).

**Independent Test**: Can be tested by creating policies with operations in non-traditional phase configurations and verifying they execute correctly.

**Acceptance Scenarios**:

1. **Given** a policy with `audio_filter` in a phase named "pre-transcode", **When** processing, **Then** audio filtering runs as part of that phase.
2. **Given** a policy with two separate transcode phases, **When** processing, **Then** both transcode operations execute in order.
3. **Given** a policy with container conversion after transcoding, **When** processing, **Then** the final output uses the specified container.
4. **Given** a phase with multiple operations (container + audio_filter + subtitle_filter), **When** processing, **Then** all operations in that phase execute in the defined order.

---

### User Story 4 - Global Configuration (Priority: P2)

As a user, I want settings like language preferences and commentary patterns to be defined once and shared across all phases so that I don't repeat configuration in every phase.

**Why this priority**: Reduces duplication and potential for inconsistency. While policies could work with repeated configuration, global config is a significant usability improvement.

**Independent Test**: Can be tested by creating a policy with global config and verifying all phases use those settings without explicit per-phase configuration.

**Acceptance Scenarios**:

1. **Given** global config with `audio_language_preference: [eng, und]`, **When** any phase evaluates audio tracks, **Then** it uses this preference.
2. **Given** global config with `on_error: fail`, **When** any phase encounters an error, **Then** processing stops immediately.
3. **Given** global config with `on_error: continue`, **When** a phase encounters a non-fatal error, **Then** processing continues to the next phase.

---

### User Story 5 - Selective Phase Execution (Priority: P2)

As a user, I want to run only specific phases from my policy so that I can re-run part of a workflow without repeating completed steps.

**Why this priority**: Enables incremental processing and recovery from partial failures without re-running expensive operations.

**Independent Test**: Can be tested by running `vpo process --phases transcode` and verifying only the transcode phase executes.

**Acceptance Scenarios**:

1. **Given** a policy with phases (normalize, synthesize, transcode), **When** I run `vpo process --phases transcode`, **Then** only the transcode phase executes.
2. **Given** a policy with phases, **When** I run `vpo process --phases normalize,synthesize`, **Then** only those two phases execute in order.
3. **Given** `--phases invalid-name`, **When** running the command, **Then** an error indicates the phase name doesn't exist in the policy.

---

### User Story 6 - GUI Phase Editor (Priority: P3)

As a user editing policies in the web UI, I want to add/remove/reorder phases visually so that I can build complex workflows without writing YAML manually.

**Why this priority**: Improves accessibility for users less comfortable with YAML, but command-line functionality must work first.

**Independent Test**: Can be tested by using the web UI to create a multi-phase policy, saving it, and verifying the YAML output is valid and matches the GUI configuration.

**Acceptance Scenarios**:

1. **Given** the policy editor, **When** I click "Add Phase", **Then** a new phase appears with a name input and operation configuration options.
2. **Given** multiple phases in the editor, **When** I drag a phase to reorder, **Then** the YAML preview updates to reflect the new order.
3. **Given** a phase with operations configured, **When** I save, **Then** the YAML output matches what the GUI displayed.

---

### Edge Cases

- **Empty phase**: A phase with no operations is skipped with a warning logged.
- **Same operation in multiple phases**: Each instance runs independently (e.g., two separate transcode phases each execute their own transcode operation).
- **Duplicate phase names**: Validation error on policy load - phase names must be unique.
- **Empty phases array**: Validation error - at least one phase is required.
- **File modified between phases**: System re-introspects the file between phases that modify it, so subsequent phases see updated track information.
- **Phase name conflicts with reserved words**: Phase names like "config" or "schema_version" are rejected as reserved.
- **Mid-phase operation failure**: If an operation fails after earlier operations in the same phase have modified the file, all changes from that phase are rolled back before `on_error` logic is evaluated.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Policy schema MUST support a `phases` array where each entry is a named phase with operations.
- **FR-002**: Phase names MUST be user-defined strings containing only alphanumeric characters, hyphens, and underscores.
- **FR-003**: Phase names MUST be unique within a policy; duplicate names cause a validation error.
- **FR-004**: Phases MUST execute in the order they appear in the policy file.
- **FR-005**: Any operation (transcription, container, audio_filter, subtitle_filter, attachment_filter, track_order, default_flags, conditional, audio_synthesis, transcode) MUST be allowed in any phase.
- **FR-006**: A single phase MAY contain multiple operations; they execute in a defined order within the phase.
- **FR-007**: Global configuration (`config:` section) MUST be available to all phases.
- **FR-008**: The system MUST report which phase is currently executing in logs and progress output.
- **FR-009**: The system MUST validate that required global config is present when operations need it.
- **FR-010**: The `--phases` CLI flag MUST allow filtering to run only specific named phases.
- **FR-011**: The system MUST NOT support the old V1-V10 flat schema; schema version 11 is required for this feature.
- **FR-012**: Phases with no operations MUST be skipped with a warning logged.
- **FR-013**: The system MUST re-introspect files between phases that modify them.
- **FR-014**: Error messages MUST indicate which phase and operation failed.
- **FR-015**: When an operation fails mid-phase, the system MUST rollback all operations in that phase, restoring the file to its pre-phase state before applying `on_error` behavior.

### Non-Functional Requirements

- **NFR-001**: Phase dispatch overhead MUST be negligible (< 100ms total for 10 phases).
- **NFR-002**: Policy validation MUST complete within 1 second for policies with up to 20 phases.

### Key Entities

- **Phase**: A named container for one or more operations. Has a unique name and an ordered list of operations to execute.
- **Operation**: A specific action to perform on media files (e.g., transcode, audio_filter, container conversion). Operations are the same as existing VPO operations but can now appear in any phase.
- **Global Config**: Shared settings (language preferences, error handling, commentary patterns) available to all phases.
- **Policy**: The top-level entity containing schema version, global config, and an ordered list of phases.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can define and execute a 6-phase workflow with a single command invocation.
- **SC-002**: Processing a file through 10 phases adds less than 100ms overhead compared to direct operation execution.
- **SC-003**: Policy validation for a 20-phase policy completes in under 1 second.
- **SC-004**: 100% of existing operations (container, audio_filter, subtitle_filter, attachment_filter, track_order, default_flags, conditional, audio_synthesis, transcode, transcription) work within user-defined phases.
- **SC-005**: Error messages always identify the specific phase and operation that failed.
- **SC-006**: Users can selectively run specific phases using the `--phases` flag without errors.

## Out of Scope

- Phase dependencies or conditional phase execution (phases always run in order)
- Parallel phase execution
- Phase templates or inheritance
- Per-phase error handling overrides (use global `on_error`)
- Backward compatibility with V1-V10 flat schema

## Schema Example

```yaml
schema_version: 11

config:
  audio_language_preference: [eng, und]
  subtitle_language_preference: [eng, und]
  commentary_patterns: [commentary, director, "audio description"]
  on_error: continue

phases:
  - name: analyze
    transcription:
      enabled: true

  - name: normalize
    container:
      target: mkv
    audio_filter:
      languages: [eng, und]
      minimum: 1
      fallback:
        mode: content_language
    subtitle_filter:
      languages: [eng, und]
      preserve_forced: true
    attachment_filter:
      remove_all: true

  - name: organize
    track_order:
      - video
      - audio_main
      - audio_alternate
      - subtitle_main
      - subtitle_forced
      - audio_commentary
      - subtitle_commentary
    default_flags:
      set_first_video_default: true
      set_preferred_audio_default: true

  - name: synthesize
    audio_synthesis:
      tracks:
        - name: "EAC3 5.1 Compatibility"
          codec: eac3
          channels: "5.1"
          bitrate: "640k"
          skip_if_exists:
            codec: [eac3]
            channels: { gte: 6 }
            language: [eng, und]
          source:
            prefer:
              - language: [eng, und]
              - codec: [truehd, dts-hd, flac]
              - channels: max

  - name: transcode
    transcode:
      video:
        target_codec: hevc
        skip_if:
          codec_matches: [hevc, h265]
        quality:
          mode: crf
          crf: 20
          preset: medium
        hardware_acceleration:
          enabled: auto
          fallback_to_cpu: true
      audio:
        preserve_codecs: [truehd, dts-hd, flac, eac3]
        transcode_to: aac
        transcode_bitrate: 192k

  - name: finalize
    conditional:
      - name: force_english_subs_for_foreign_audio
        when:
          or:
            - audio_is_multi_language:
                threshold: 0.05
            - not:
                exists:
                  track_type: audio
                  language: eng
                  is_default: true
        then:
          - set_forced:
              track_type: subtitle
              language: eng
              value: true
```

## Assumptions

- The `vpo process` command will be the primary entry point (may require renaming or aliasing existing commands).
- Schema version 11 will be a breaking change; users must migrate their V10 policies to the new structure.
- The order of operations within a phase follows a predefined sequence (container → filters → track_order → default_flags → conditional → synthesis → transcode → transcription) unless otherwise specified.
- Re-introspection between phases only occurs when a phase modifies the file; read-only phases (like analyze) don't trigger re-introspection.
