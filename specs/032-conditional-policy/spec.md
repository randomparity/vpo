# Feature Specification: Conditional Policy Logic

**Feature Branch**: `032-conditional-policy`
**Created**: 2025-11-26
**Status**: Draft
**Input**: User description: "Sprint 2: Conditional Policy Logic - Implement if/then/else rules in VPO policies for smart decisions based on file analysis"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Basic Conditional Rules (Priority: P1)

As a power user, I want to apply different settings based on file properties so that one policy handles multiple scenarios without needing separate policies.

**Why this priority**: This is the core capability that enables all other conditional features. Without the fundamental if/then structure, no other conditional logic can work.

**Independent Test**: Can be fully tested by creating a policy with a single conditional rule that checks for video resolution and applies different CRF values. Delivers immediate value by eliminating the need for multiple policy files.

**Acceptance Scenarios**:

1. **Given** a policy with a `conditional` section containing a named rule with `when` and `then` clauses, **When** the policy is applied to a file that matches the condition, **Then** the actions in the `then` clause are executed.
2. **Given** a policy with a conditional rule that has an `else` clause, **When** the policy is applied to a file that does NOT match the condition, **Then** the actions in the `else` clause are executed.
3. **Given** a policy with multiple conditional rules, **When** the policy is applied, **Then** rules are evaluated in order and the first matching rule's actions are applied.
4. **Given** a policy with conditional rules and `--dry-run` flag, **When** the policy is evaluated, **Then** the output shows which rules matched and why.

---

### User Story 2 - Track Existence Conditions (Priority: P1)

As a media manager, I want to check whether specific tracks exist before taking action so that I don't create duplicate tracks or miss required processing.

**Why this priority**: Track existence checking (`exists` and `not exists`) is the most common condition type and enables practical use cases like "add stereo if missing."

**Independent Test**: Can be tested by creating a condition that checks for the existence of an English audio track. Delivers value by enabling smart track-aware decisions.

**Acceptance Scenarios**:

1. **Given** a condition with `exists` checking for a track type with specific properties, **When** a file contains a matching track, **Then** the condition evaluates to true.
2. **Given** a condition with `not: { exists: ... }`, **When** a file lacks any matching track, **Then** the condition evaluates to true.
3. **Given** a condition checking for track existence, **When** dry-run is enabled, **Then** output shows "Skipping [action] - compatible track exists" or "No matching track found."

---

### User Story 3 - Boolean Operators (Priority: P2)

As a Japanese content collector, I want to combine multiple conditions with AND/OR logic so that I can express complex requirements like "Japanese primary audio AND English subtitles exist."

**Why this priority**: Boolean operators extend the expressive power of conditions significantly, but basic single conditions are still useful without them.

**Independent Test**: Can be tested by creating an `and` condition combining two existence checks. Delivers value by enabling multi-criteria decisions.

**Acceptance Scenarios**:

1. **Given** a condition using `and` with two sub-conditions, **When** both conditions are true, **Then** the overall condition evaluates to true.
2. **Given** a condition using `and` with two sub-conditions, **When** only one condition is true, **Then** the overall condition evaluates to false.
3. **Given** a condition using `or` with two sub-conditions, **When** at least one condition is true, **Then** the overall condition evaluates to true.
4. **Given** a condition using `not` wrapping another condition, **When** the inner condition is false, **Then** the overall condition evaluates to true.

---

### User Story 4 - Comparison Operators for Properties (Priority: P2)

As a 4K collector, I want to compare numeric track properties using operators like greater-than and less-than so that I can make resolution-based or channel-count-based decisions.

**Why this priority**: Numeric comparisons enable resolution-based and quality-based logic, which are common use cases but require the basic condition framework first.

**Independent Test**: Can be tested by creating a condition checking `height: { gte: 2160 }` for 4K detection. Delivers value by enabling resolution-aware processing.

**Acceptance Scenarios**:

1. **Given** a condition with `width: { gte: 3840 }`, **When** a video track has width of 3840 or more, **Then** the condition evaluates to true.
2. **Given** a condition with `height: { lt: 2160 }`, **When** a video track has height below 2160, **Then** the condition evaluates to true.
3. **Given** comparison operators (`eq`, `lt`, `lte`, `gt`, `gte`), **When** applied to numeric properties like channels, width, height, **Then** correct comparisons are performed.

---

### User Story 5 - Track Count Conditions (Priority: P2)

As an audio engineer, I want to apply rules based on the number of audio tracks so that I can handle files with single vs multiple audio tracks differently.

**Why this priority**: Track counting extends existence checks to quantity-based logic, useful for distinguishing between simple files and complex multi-track files.

**Independent Test**: Can be tested by creating a condition `count: { track_type: audio, gt: 1 }` to detect multi-audio files. Delivers value by enabling count-based decisions.

**Acceptance Scenarios**:

1. **Given** a condition with `count: { track_type: audio, eq: 1 }`, **When** a file has exactly one audio track, **Then** the condition evaluates to true.
2. **Given** a condition with `count: { track_type: audio, gt: 1 }`, **When** a file has multiple audio tracks, **Then** the condition evaluates to true.
3. **Given** count conditions with filters like `language: eng`, **When** counting, **Then** only matching tracks are counted.

---

### User Story 6 - Skip Processing Actions (Priority: P3)

As a storage optimizer, I want to skip video transcoding when the file is already in the target codec so that I avoid unnecessary quality loss and processing time.

**Why this priority**: Skip actions are valuable optimizations but require the core condition evaluation to be working first.

**Independent Test**: Can be tested by creating a rule that sets `skip_video_transcode: true` when codec is HEVC. Delivers value by avoiding wasteful re-encoding.

**Acceptance Scenarios**:

1. **Given** a condition matching HEVC codec with action `skip_video_transcode: true`, **When** a file already has HEVC video, **Then** video transcoding is skipped.
2. **Given** a skip action for video, **When** dry-run is enabled, **Then** output shows "Skipping video transcode - already HEVC."
3. **Given** a skip video action is triggered, **When** the policy is applied, **Then** audio and subtitle processing still proceeds normally.
4. **Given** a condition checking codec against a list like `[hevc, h265, x265]`, **When** the track codec matches any alias, **Then** the condition evaluates to true.

---

### User Story 7 - Conditional Warnings and Errors (Priority: P3)

As a careful operator, I want to generate warnings or halt processing when certain conditions are met so that I can review problematic files manually.

**Why this priority**: Warning and error actions are useful for quality control but are not required for basic conditional policy operation.

**Independent Test**: Can be tested by creating a rule with `warn: "message"` action. Delivers value by enabling quality gates.

**Acceptance Scenarios**:

1. **Given** a conditional rule with `warn: "message"` action, **When** the condition matches, **Then** the warning is logged and processing continues.
2. **Given** a conditional rule with `fail: "message"` action, **When** the condition matches, **Then** processing stops with the error message.
3. **Given** a message containing `{filename}` placeholder, **When** the warning/error is emitted, **Then** the placeholder is replaced with the actual file name.
4. **Given** warnings in a policy, **When** dry-run is enabled, **Then** warnings are visible in the output.

---

### Edge Cases

- What happens when no conditional rules match and there's no else clause? (Processing continues with other policy sections)
- What happens when multiple rules could match? (First matching rule wins; subsequent rules are not evaluated)
- How does system handle conditions on missing track properties? (Condition evaluates to false if property doesn't exist)
- What happens when a condition references an unknown track type? (Validation error at policy load time)
- How are empty conditional sections handled? (Treated as no-op; policy processes normally without conditional logic)
- What happens when `then` or `else` clause is empty? (No-op for that branch; used for "match but do nothing")

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Policy schema MUST support a `conditional` section containing a list of named rules
- **FR-002**: Each conditional rule MUST have a `name` (string), `when` (condition), and `then` (actions) field
- **FR-003**: Each conditional rule MAY have an optional `else` (actions) field for fallback behavior
- **FR-004**: System MUST evaluate conditional rules in document order, stopping at the first match
- **FR-005**: System MUST support `exists` condition type to check for presence of tracks matching criteria
- **FR-006**: System MUST support `not` operator to negate any condition
- **FR-007**: System MUST support `and` operator combining multiple conditions (all must be true)
- **FR-008**: System MUST support `or` operator combining multiple conditions (at least one must be true)
- **FR-009**: System MUST support comparison operators (`eq`, `lt`, `lte`, `gt`, `gte`) for numeric track properties
- **FR-010**: Comparison operators MUST work with properties: `channels`, `width`, `height`, and other numeric track fields
- **FR-011**: System MUST support `count` condition type to check the number of tracks matching criteria
- **FR-012**: System MUST recognize codec aliases (e.g., hevc/h265/x265 are equivalent) in condition matching
- **FR-013**: System MUST support `skip_video_transcode: true` action to bypass video processing
- **FR-014**: System MUST support `warn: "message"` action to log a warning and continue processing
- **FR-015**: System MUST support `fail: "message"` action to halt processing with an error
- **FR-016**: Warning and error messages MUST support `{filename}` placeholder substitution
- **FR-017**: Dry-run mode MUST display which conditional rules matched and the reason
- **FR-018**: System MUST validate conditional syntax at policy load time and report clear errors
- **FR-019**: Conditions MUST be able to check track properties including: `track_type`, `language`, `codec`, `is_default`, `channels`, `width`, `height`
- **FR-020**: Boolean operator nesting MUST be limited to a maximum depth of 3 levels; deeper nesting produces a validation error at policy load time
- **FR-021**: Conditional rules MUST be evaluated before non-conditional policy sections; conditionals may set flags that influence subsequent processing, but non-conditional sections always execute

### Key Entities

- **ConditionalRule**: A named rule with a condition (`when`) and actions (`then`/`else`). Rules are evaluated in order.
- **Condition**: An expression that evaluates to true/false. Can be `exists`, `count`, `not`, `and`, `or`, or a comparison.
- **TrackMatcher**: Criteria for matching tracks within conditions - combines track type with property filters.
- **ConditionalAction**: An action triggered by a condition - can be policy operations like `transcode`, control actions like `skip_video_transcode`, or alerts like `warn`/`fail`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can write a single policy that handles both 4K and 1080p content with different settings, eliminating the need for resolution-specific policies
- **SC-002**: Users can define "add stereo if missing" logic that correctly skips files already having stereo audio in 100% of test cases
- **SC-003**: Dry-run output clearly shows conditional evaluation with rule names and match/no-match status for each rule
- **SC-004**: Invalid conditional syntax produces clear, actionable error messages at policy load time within 1 second
- **SC-005**: Complex conditions combining 3+ operators (e.g., `and` with nested `exists` and `not`) evaluate correctly in 100% of test cases
- **SC-006**: Processing files with skip actions completes without performing the skipped operation while still completing other operations
- **SC-007**: Warning actions appear in both dry-run and execution output with proper file name substitution

## Clarifications

### Session 2025-11-26

- Q: How deep should condition nesting be allowed? → A: Maximum 3 levels deep
- Q: How should conditional and non-conditional policy sections interact? → A: Conditionals execute first (may set flags), then non-conditional sections always execute

## Assumptions

- **A-001**: This feature builds on Sprint 1 (Track Filtering) infrastructure for track analysis and matching
- **A-002**: Codec alias mapping (hevc/h265/x265) follows industry-standard naming conventions
- **A-003**: Track properties available for conditions are those already extracted by ffprobe introspection
- **A-004**: The `then` actions use the same syntax as existing policy action sections
- **A-005**: Conditional rules are evaluated once per file, not per-track
- **A-006**: When no rules match and no else exists, processing continues with the rest of the policy (non-conditional sections still apply)
