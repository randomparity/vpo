# Feature Specification: V9 Policy Editor GUI

**Feature Branch**: `036-v9-policy-editor`
**Created**: 2025-11-30
**Status**: Draft
**Input**: User description: "The policy schema has experienced several significant updates to provide more functionality, but the policies page of the GUI has not been updated to keep pace. As a user I would like to be able to have a GUI method to create/edit policies that support schema v9 in order to manage the policies on my vpo installation."

## User Scenarios & Testing

### User Story 1 - Edit V6 Video Transcode Settings (Priority: P1)

As a user managing my video library, I want to configure video transcoding settings through the GUI so that I can set up conditional transcoding without manually editing YAML files.

**Why this priority**: Video transcoding is the most complex and commonly used feature added since the original editor. Users need visual guidance for skip conditions, quality settings, scaling, and hardware acceleration options.

**Independent Test**: Can be fully tested by creating a policy with video transcode settings, verifying the GUI displays all V6 video fields correctly, modifying settings, and confirming the saved YAML matches expectations.

**Acceptance Scenarios**:

1. **Given** a policy with existing V6 video transcode config, **When** I open the policy editor, **Then** I see the video transcode section with all fields populated (target_codec, skip_if, quality, scaling, hardware_acceleration).

2. **Given** the policy editor is open, **When** I configure skip conditions (codec_matches, resolution_within, bitrate_under), **Then** the YAML preview updates to show the skip_if block with my selections.

3. **Given** the policy editor is open, **When** I set quality settings (mode: crf/bitrate/constrained_quality, crf value, preset, tune), **Then** validation prevents invalid combinations (e.g., bitrate mode without bitrate value).

4. **Given** I configure scaling settings with max_resolution "1080p", **When** I save the policy, **Then** the scaling section is correctly written to YAML.

---

### User Story 2 - Edit V6 Audio Transcode Settings (Priority: P1)

As a user, I want to configure audio transcoding settings through the GUI so that I can specify which codecs to preserve and how to handle non-preserved tracks.

**Why this priority**: Audio transcode settings work alongside video transcode and are essential for complete transcoding configuration.

**Independent Test**: Can be fully tested by editing audio transcode settings (preserve_codecs, transcode_to, transcode_bitrate) and verifying the saved policy correctly reflects the changes.

**Acceptance Scenarios**:

1. **Given** a policy with V6 audio transcode config, **When** I open the editor, **Then** I see preserve_codecs as a list with add/remove controls, and transcode_to/transcode_bitrate as dropdown/input fields.

2. **Given** I add "truehd" to preserve_codecs list, **When** I save, **Then** the policy file contains the updated preserve_codecs array.

3. **Given** I enter an invalid bitrate format (e.g., "abc"), **When** I try to save, **Then** validation fails with a clear error message indicating the correct format.

---

### User Story 3 - Edit V5 Audio Synthesis Configuration (Priority: P2)

As a user with complex audio requirements, I want to configure audio synthesis tracks through the GUI so that I can create downmixed or re-encoded audio tracks automatically.

**Why this priority**: Audio synthesis is a powerful feature for users who need compatibility tracks (e.g., stereo downmix from surround), but is less commonly used than basic transcoding.

**Independent Test**: Can be fully tested by adding a synthesis track definition with name, codec, channels, source preferences, and verifying it saves correctly.

**Acceptance Scenarios**:

1. **Given** a policy without audio_synthesis, **When** I click "Add Synthesis Track", **Then** I see a form with fields for name, codec (dropdown), channels, source preferences, and optional fields (bitrate, title, language, position).

2. **Given** I configure a synthesis track with source.prefer criteria (language, not_commentary, channels), **When** I save, **Then** the YAML contains the correctly structured audio_synthesis.tracks entry.

3. **Given** I configure skip_if_exists criteria (V8 feature), **When** I save, **Then** the skip_if_exists block is correctly written with codec, channels comparison, language, and not_commentary fields.

---

### User Story 4 - Edit V4 Conditional Rules (Priority: P2)

As a user with varied content, I want to configure conditional rules through the GUI so that I can apply different processing based on file characteristics.

**Why this priority**: Conditional rules enable sophisticated workflows but require understanding of condition syntax. GUI guidance helps users construct valid rules.

**Independent Test**: Can be fully tested by creating a conditional rule with when condition, then actions, and optionally else actions, then verifying the saved YAML.

**Acceptance Scenarios**:

1. **Given** the policy editor is open, **When** I add a conditional rule, **Then** I see a form with name input, condition builder (exists/count/and/or/not), and action selectors.

2. **Given** I create a rule with condition "exists: audio, language: jpn", **When** I add action "skip_video_transcode: true", **Then** the YAML preview shows the correctly structured conditional rule.

3. **Given** I configure an audio_is_multi_language condition (V7), **When** I set threshold and primary_language, **Then** validation accepts the configuration and saves correctly.

---

### User Story 5 - Edit V3 Track Filtering Configuration (Priority: P2)

As a user, I want to configure track filtering through the GUI so that I can remove unwanted tracks by language or type.

**Why this priority**: Track filtering is a core feature for managing multi-language content but was added in V3 and is not currently editable in the GUI.

**Independent Test**: Can be fully tested by configuring audio_filter, subtitle_filter, and attachment_filter sections and verifying the saved policy.

**Acceptance Scenarios**:

1. **Given** the policy editor is open, **When** I configure audio_filter with languages and fallback mode, **Then** the YAML preview shows the audio_filter block.

2. **Given** I configure subtitle_filter with languages and preserve_forced: true, **When** I save, **Then** the policy file contains the correct subtitle_filter configuration.

3. **Given** I enable attachment_filter.remove_all, **When** I save, **Then** attachments will be removed when the policy is applied.

---

### User Story 6 - Edit V3 Container Configuration (Priority: P3)

As a user, I want to configure container format conversion through the GUI so that I can remux files to MKV or MP4.

**Why this priority**: Container conversion is useful but less frequently configured than track filtering or transcoding.

**Independent Test**: Can be fully tested by setting container.target and container.on_incompatible_codec, then verifying the saved YAML.

**Acceptance Scenarios**:

1. **Given** the policy editor is open, **When** I select container target "mp4", **Then** I see options for on_incompatible_codec (error/skip/transcode).

2. **Given** I set container.on_incompatible_codec to "skip", **When** I save, **Then** the policy file contains the container configuration.

---

### User Story 7 - Edit V9 Workflow Configuration (Priority: P3)

As a user running the VPO daemon, I want to configure workflow settings through the GUI so that I can control processing phases and error handling.

**Why this priority**: Workflow configuration is daemon-specific and only relevant for users running `vpo serve` with auto-processing enabled.

**Independent Test**: Can be fully tested by configuring workflow.phases, auto_process, and on_error, then verifying the saved YAML.

**Acceptance Scenarios**:

1. **Given** the policy editor is open, **When** I enable workflow configuration, **Then** I can select phases (analyze, apply, transcode) and their order.

2. **Given** I enable auto_process and set on_error to "continue", **When** I save, **Then** the workflow section is correctly written to YAML.

---

### User Story 8 - Create New Policy (Priority: P3)

As a user, I want to create new policies through the GUI so that I can set up new configurations without copying and editing YAML files manually.

**Why this priority**: Creating new policies is less frequent than editing existing ones, and users can currently copy policy files manually.

**Independent Test**: Can be fully tested by clicking "Create New Policy", entering a name, configuring settings, and verifying a new policy file is created.

**Acceptance Scenarios**:

1. **Given** I am on the policies list page, **When** I click "Create New Policy", **Then** I see a form to enter the policy name and configure initial settings.

2. **Given** I enter a valid policy name and configure settings, **When** I save, **Then** a new policy file is created in the policies directory with the latest supported schema_version.

3. **Given** I enter a policy name that already exists, **When** I try to save, **Then** I see an error message and the existing policy is not overwritten.

---

### Edge Cases

- What happens when a policy file is edited externally while the GUI editor is open? (Concurrent modification detection via last_modified timestamp)
- How does the editor handle policies with unknown fields from future schema versions? (Preserve unknown fields, display warning)
- What happens if validation fails on save? (Display field-level errors, highlight affected sections)
- How are V10 music/sfx/non_speech audio filter options displayed? (Show in audio_filter section when schema_version >= 10)

## Requirements

### Functional Requirements

- **FR-001**: System MUST display all V6 video transcode fields (target_codec, skip_if, quality, scaling, hardware_acceleration) when editing a policy with video transcode configuration.

- **FR-002**: System MUST validate quality settings mode requirements (bitrate required for bitrate mode, no conflicting crf+bitrate in crf mode).

- **FR-003**: System MUST display all V6 audio transcode fields (preserve_codecs, transcode_to, transcode_bitrate) with appropriate input controls.

- **FR-004**: System MUST support adding, editing, and removing audio synthesis track definitions (V5+).

- **FR-005**: System MUST support skip_if_exists criteria in synthesis tracks (V8+).

- **FR-006**: System MUST provide a condition builder for V4 conditional rules supporting exists, count, and/or/not conditions with up to two levels of nesting (e.g., an "and" or "or" containing leaf conditions like exists/count).

- **FR-007**: System MUST support V7 condition types (audio_is_multi_language) and actions (set_forced, set_default).

- **FR-008**: System MUST support V8 not_commentary filter in conditions and synthesis source preferences.

- **FR-009**: System MUST display V3 track filtering options (audio_filter, subtitle_filter, attachment_filter) with appropriate controls.

- **FR-010**: System MUST display V3 container configuration options (target, on_incompatible_codec).

- **FR-011**: System MUST display V9 workflow configuration options (phases, auto_process, on_error).

- **FR-012**: System MUST support creating new policies with a user-specified name, defaulting to the latest supported schema version (currently 10).

- **FR-013**: System MUST preserve unknown fields and best-effort preserve comments during round-trip editing.

- **FR-014**: System MUST validate all inputs against schema constraints and display field-level error messages.

- **FR-015**: System MUST update the YAML preview in real-time as the user edits (with appropriate debouncing).

- **FR-016**: System MUST detect concurrent modifications and warn the user before overwriting.

- **FR-017**: System MUST display validation errors from both client-side and server-side validation.

- **FR-018**: System MUST organize new schema sections (transcode, synthesis, conditional rules, filtering, container, workflow) as collapsible accordion sections that expand on demand.

### Key Entities

- **PolicySchema**: The validated policy configuration containing all schema fields from V1-V10.
- **VideoTranscodeConfig**: V6 video transcoding settings including skip conditions, quality, scaling, and hardware acceleration.
- **AudioTranscodeConfig**: V6 audio transcoding settings for codec preservation and transcoding.
- **AudioSynthesisConfig**: V5 audio synthesis configuration with track definitions.
- **ConditionalRule**: V4 conditional processing rules with conditions and actions.
- **AudioFilterConfig**: V3 audio track filtering with V10 music/sfx/non_speech support.
- **SubtitleFilterConfig**: V3 subtitle track filtering.
- **ContainerConfig**: V3 container format conversion settings.
- **WorkflowConfig**: V9 workflow phase and error handling configuration.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Users can configure all V6-V9 schema features through the GUI without editing YAML manually.

- **SC-002**: 90% of policy configurations that pass server-side validation can be created through the GUI.

- **SC-003**: Users can complete the following tasks in under 5 minutes each: (a) add video transcode settings with skip conditions, (b) configure audio language filtering, (c) create a conditional rule with one condition and action.

- **SC-004**: Validation errors are displayed within 500ms of user input, with clear field-level messages.

- **SC-005**: Round-trip editing preserves all unknown fields and at least 90% of YAML comments.

- **SC-006**: In usability testing, at least 80% of new users can create a working policy with video transcode settings without consulting documentation or requiring assistance.

## Clarifications

### Session 2025-11-30

- Q: How should the many schema sections be organized in the editor UI? → A: Collapsible accordion sections that expand on demand
- Q: What level of nesting should the conditional rules builder support? → A: Two levels of nesting (e.g., and/or containing exists/count conditions)
- Q: What schema version should new policies use by default? → A: Latest supported version (currently 10)

## Assumptions

- Users have basic familiarity with video/audio codecs and media file concepts.
- The existing PolicyRoundTripEditor infrastructure will be extended rather than replaced.
- The GUI will use the same vanilla JavaScript approach as the existing policy editor (no frameworks).
- Server-side validation using Pydantic models will be the authoritative validation source.
- The existing API endpoints (/api/policies/{name}) will be extended to handle new schema fields.
