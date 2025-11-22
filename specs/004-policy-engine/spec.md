# Feature Specification: Policy Engine & Reordering (Dry-Run & Metadata-Only)

**Feature Branch**: `004-policy-engine`
**Created**: 2025-11-22
**Status**: Draft
**Input**: User description: "Implement a policy engine that can simulate changes and apply metadata-only operations (e.g., track order, default flags, titles) without heavy transcoding."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dry-Run Policy Preview (Priority: P1)

As a cautious user, I want to preview what changes a policy would make to my media files without actually modifying them so that I can verify policies are working correctly before committing changes.

**Why this priority**: This is the safest entry point for users to interact with the policy system. Without dry-run capability, users risk unintended modifications to their media library. This builds trust and enables iterative policy refinement.

**Independent Test**: Can be fully tested by running a dry-run command against a media file with a policy and verifying the output shows proposed changes without modifying the file.

**Acceptance Scenarios**:

1. **Given** a media file with tracks and a policy file defining track ordering rules, **When** the user runs the apply command with --dry-run flag, **Then** the system displays a before/after comparison showing proposed track reordering without modifying the file.
2. **Given** a policy that would change default audio track flags, **When** running in dry-run mode, **Then** the output clearly shows which track would become the new default and which would lose its default flag.
3. **Given** a media file that already matches the policy, **When** running dry-run, **Then** the system reports "No changes required" rather than showing empty diffs.

---

### User Story 2 - Policy Definition (Priority: P1)

As a power user, I want to define track ordering and selection rules in a configuration file so that I can apply consistent policies across my entire media library.

**Why this priority**: Users need a way to express their preferences before the engine can evaluate them. This is a prerequisite for all policy evaluation functionality.

**Independent Test**: Can be tested by creating a policy file and validating it loads without errors and represents the expected rules.

**Acceptance Scenarios**:

1. **Given** a policy file with a track_order section, **When** the policy is loaded, **Then** the system understands the desired ordering of track types (video first, then main audio, alternate audio, subtitles, commentary).
2. **Given** a policy file with audio_language_preference list, **When** the policy is loaded, **Then** the system uses this list to determine which audio track should be marked as default.
3. **Given** a policy file with commentary_keywords list, **When** evaluating tracks, **Then** the system identifies commentary tracks by matching track titles against the keywords.
4. **Given** a malformed policy file, **When** attempting to load it, **Then** the system reports specific validation errors indicating what is wrong.

---

### User Story 3 - Metadata Application (Priority: P2)

As a user, I want the tool to write metadata-only changes (track titles, languages, default flags) to my files so that my library becomes more consistent without time-consuming transcoding.

**Why this priority**: Once users trust the dry-run output, they need the ability to actually apply changes. Metadata operations are fast and low-risk compared to transcoding, making this the natural next step.

**Independent Test**: Can be tested by applying a policy to a test file and verifying the file's metadata has changed while the actual media streams remain untouched.

**Acceptance Scenarios**:

1. **Given** a policy that changes the default audio track, **When** the user runs apply without --dry-run, **Then** the file's metadata is updated to reflect the new default flag settings.
2. **Given** a policy that sets track titles, **When** applied to a file, **Then** the track titles in the container are updated to match the policy.
3. **Given** a metadata change is applied, **When** checking the database, **Then** the applied operation is recorded with timestamp, file path, and changes made.
4. **Given** a metadata application fails mid-operation, **When** the failure occurs, **Then** the original file remains unchanged and the error is logged.

---

### User Story 4 - Track Reordering (Priority: P2)

As a user, I want tracks reordered according to my policy so that my media files have a consistent structure (video first, preferred audio second, etc.).

**Why this priority**: Track reordering is a key policy outcome that improves user experience with media players. This is more complex than simple flag changes but still avoids transcoding.

**Independent Test**: Can be tested by applying a reordering policy to a test file and verifying the track order has changed.

**Acceptance Scenarios**:

1. **Given** a file with audio tracks before video tracks, **When** a policy requiring video-first ordering is applied, **Then** the tracks are reordered with video first.
2. **Given** a policy with audio_language_preference of ["eng", "jpn"], **When** applied to a file with Japanese audio first and English audio second, **Then** the English audio track is moved to the primary audio position.
3. **Given** tracks are reordered, **When** the operation completes, **Then** the media streams themselves are not re-encoded (file size change is minimal, only container-level changes).

---

### User Story 5 - Policy Evaluation Engine (Priority: P2)

As a developer, I want a pure-function policy evaluation engine that maps current track state to desired state so that policy behavior is predictable, testable, and consistent.

**Why this priority**: A clean separation between evaluation (determining what should change) and execution (making changes) enables thorough testing and debugging. This architectural choice supports reliability.

**Independent Test**: Can be tested by calling the evaluation function with mock track data and a policy, verifying the returned plan matches expectations.

**Acceptance Scenarios**:

1. **Given** track metadata and a policy configuration, **When** calling the evaluate function, **Then** it returns a plan describing all needed changes (reordering, flag changes, title updates).
2. **Given** the same inputs, **When** calling evaluate multiple times, **Then** the function returns identical plans (deterministic behavior).
3. **Given** a plan returned by evaluate, **When** examining the plan structure, **Then** each change is described with before-state, after-state, and change type.

---

### Edge Cases

- What happens when a policy references a language not present in the file? System should skip the preference and move to the next language in the list.
- What happens when all audio tracks are identified as commentary? System should use the first audio track as default rather than leaving no default.
- How does system handle files with no audio tracks? Track ordering proceeds with available track types; audio-specific rules are skipped.
- What happens when track reordering fails mid-operation? System should restore the original file from backup and report the failure.
- What happens when a policy file doesn't define any rules? System should validate and warn that the policy has no effect.
- How does system handle concurrent policy applications to the same file? System should lock the file during modification to prevent corruption.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support policy files that define track ordering preferences.
- **FR-002**: System MUST support policy files that define audio language preferences as an ordered list.
- **FR-003**: System MUST support policy files that define patterns for identifying commentary tracks; patterns are user-defined regex with case-insensitive substring matching as the default behavior.
- **FR-004**: System MUST validate policy files on load and report specific errors for malformed policies.
- **FR-005**: System MUST provide a dry-run mode that shows proposed changes without modifying files.
- **FR-006**: System MUST display dry-run output as a clear before/after comparison.
- **FR-007**: System MUST implement a pure evaluation function that takes (file metadata, track list, policy) and returns a change plan.
- **FR-008**: System MUST ensure the evaluation function produces identical output for identical inputs (deterministic).
- **FR-009**: System MUST support modifying track default flags without re-encoding media streams.
- **FR-010**: System MUST support modifying track titles without re-encoding media streams.
- **FR-011**: System MUST support reordering tracks within MKV containers without re-encoding media streams; for non-MKV formats (MP4, etc.), only flag and title modifications are supported.
- **FR-012**: System MUST record all applied operations in the database with timestamp and change details.
- **FR-013**: System MUST create a backup (same directory, `.vpo-backup` suffix) before modifying files and restore on failure; backup retention after success is configurable via user profile.
- **FR-014**: System MUST report "no changes required" when a file already matches the policy.
- **FR-015**: System MUST prevent concurrent modifications to the same file.
- **FR-016**: System MUST provide a command-line interface: `vpo apply --policy <file> [--dry-run] <target>`.

### Key Entities

- **Policy**: A user-defined configuration specifying desired track organization. Key attributes include: track ordering rules, audio language preferences, commentary identification keywords, and policy version.
- **Plan**: The output of policy evaluation representing intended changes. Contains a list of planned actions (reorder, set-flag, set-title) with before and after states for each.
- **PlannedAction**: A single change to be applied. Attributes include: action type, target track, current value, desired value.
- **OperationRecord**: An audit log entry for an applied change. Attributes include: timestamp, file path, policy used, actions applied, success/failure status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can preview policy changes on any supported media file within 2 seconds.
- **SC-002**: Metadata-only operations complete within 5 seconds for files up to 50GB.
- **SC-003**: 100% of applied operations are recorded in the database for audit purposes.
- **SC-004**: Dry-run output accurately predicts actual changes (100% match when applied).
- **SC-005**: Policy evaluation produces identical results when run multiple times on the same input.
- **SC-006**: File integrity is preserved during modification failures (zero corruption from failed operations).
- **SC-007**: Users can define and validate policies without external documentation reference (self-documenting error messages).

## Clarifications

### Session 2025-11-22

- Q: Should non-MKV formats support full track reordering, or only metadata flag changes? → A: MKV: full reordering; Others: flags/titles only
- Q: How should commentary keywords be matched against track titles? → A: User-defined regex patterns with case-insensitive substring as default
- Q: Where should backups be stored and when cleaned up? → A: Same directory with .vpo-backup suffix; keep/delete behavior configurable by user profile

## Assumptions

- Media files have already been scanned and have track metadata in the database (depends on 003-media-introspection).
- The system has write access to media files being modified.
- External tools (mkvpropedit or ffmpeg) are available for container manipulation.
- Policy files use a standard format (YAML assumed based on project conventions).
- Track reordering for MKV files uses mkvpropedit; other formats may have limitations.

## Out of Scope

- Transcoding or re-encoding media streams (this feature handles metadata-only operations).
- Batch processing or library-wide policy application (single-file operations only in this feature).
- Policy inheritance or composition (complex policy hierarchies).
- Automatic policy generation or recommendations.
- GUI or web interface for policy editing.
- Language tag normalization or correction (tracks use existing language tags).
- Subtitle format conversion.
