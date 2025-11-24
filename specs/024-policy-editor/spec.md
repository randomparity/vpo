# Feature Specification: Visual Policy Editor

**Feature Branch**: `024-policy-editor`
**Created**: 2025-11-24
**Status**: Draft
**Input**: User description: "Build visual policy editor for core options - Create a visual, form-based policy editor that edits the core policy fields without requiring users to manually edit YAML/JSON."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Edit Track Ordering Rules (Priority: P1)

As a library admin, I want to configure the order in which different track types appear in my video files so that my preferred structure is automatically applied across my library.

**Why this priority**: Track ordering is the most fundamental policy setting and affects every file processed. Users need control over where video, audio, subtitles, and commentary tracks appear.

**Independent Test**: Can be fully tested by opening a policy in the editor, reordering track types via drag-and-drop or controls, saving, and verifying the YAML reflects the new order.

**Acceptance Scenarios**:

1. **Given** I open a policy in the editor, **When** I view the track ordering section, **Then** I see all track types displayed in their current order.
2. **Given** I am viewing the track ordering section, **When** I move a track type to a different position, **Then** the list updates to reflect the new order.
3. **Given** I have modified the track order, **When** I save the policy, **Then** the underlying YAML file is updated with the new track_order array.

---

### User Story 2 - Configure Audio Preferences (Priority: P1)

As a library admin, I want to set my preferred audio language order and codec priorities so that the correct audio track is selected as default when processing files.

**Why this priority**: Audio preferences directly impact user experience when playing videos. Setting the correct default audio track is a primary use case.

**Independent Test**: Can be fully tested by opening a policy, adding/removing/reordering audio languages, adjusting codec preferences, saving, and verifying the YAML reflects changes.

**Acceptance Scenarios**:

1. **Given** I open a policy in the editor, **When** I view the audio preferences section, **Then** I see the current language preference list (e.g., eng, jpn).
2. **Given** I am editing audio preferences, **When** I add a new language code (e.g., "fra"), **Then** it appears in the list and can be reordered.
3. **Given** I am editing audio preferences, **When** I remove a language from the list, **Then** it is removed from the preference order.
4. **Given** the policy has audio codec settings (in transcode section), **When** I view the audio preferences, **Then** I see which codecs are preserved vs transcoded.

---

### User Story 3 - Configure Subtitle Defaults (Priority: P2)

As a library admin, I want to set my preferred subtitle language order and forced subtitle behavior so that the correct subtitles are shown when playing videos.

**Why this priority**: Subtitle configuration is important for accessibility and multilingual libraries but is secondary to audio for most users.

**Independent Test**: Can be fully tested by opening a policy, configuring subtitle language preferences and default flags, saving, and verifying the YAML reflects changes.

**Acceptance Scenarios**:

1. **Given** I open a policy in the editor, **When** I view the subtitle preferences section, **Then** I see the current subtitle language preference list.
2. **Given** I am editing subtitle preferences, **When** I toggle "set_preferred_subtitle_default", **Then** the default flags section is updated.
3. **Given** I have modified subtitle settings, **When** I save the policy, **Then** the subtitle_language_preference and default_flags are updated in the YAML.

---

### User Story 4 - Configure Commentary Detection (Priority: P2)

As a library admin, I want to configure how commentary tracks are detected and where they are placed so that director's commentary and other special tracks are handled consistently.

**Why this priority**: Commentary handling is a valuable feature for curated libraries but not essential for basic policy editing.

**Independent Test**: Can be fully tested by editing commentary patterns (keywords), toggling commentary detection options, saving, and verifying the policy file.

**Acceptance Scenarios**:

1. **Given** I open a policy in the editor, **When** I view the commentary section, **Then** I see the current commentary_patterns list (e.g., "commentary", "director").
2. **Given** I am editing commentary settings, **When** I add a new pattern (e.g., "behind the scenes"), **Then** it is added to the patterns list.
3. **Given** the policy has transcription settings, **When** I view the commentary section, **Then** I see options for detect_commentary and reorder_commentary.

---

### User Story 5 - View Raw Policy Representation (Priority: P2)

As a library admin, I want to see a read-only view of the raw YAML representation alongside the form so that I can understand exactly what changes I'm making.

**Why this priority**: Transparency builds trust and helps users learn the policy format. Essential for power users transitioning from manual editing.

**Independent Test**: Can be fully tested by making changes in the form and verifying the read-only YAML panel updates in real-time.

**Acceptance Scenarios**:

1. **Given** I open a policy in the editor, **When** I view the page, **Then** I see a read-only panel showing the current YAML representation.
2. **Given** I make a change in the form (e.g., reorder languages), **When** the change is applied, **Then** the YAML panel updates to reflect the change.
3. **Given** I am viewing the YAML panel, **When** I attempt to edit it, **Then** the panel does not allow direct editing (read-only).

---

### User Story 6 - Save Policy Changes (Priority: P1)

As a library admin, I want to save my policy changes via the editor and receive clear feedback so that I know whether my changes were successfully persisted.

**Why this priority**: Without saving, the editor has no value. Clear feedback prevents confusion about policy state.

**Independent Test**: Can be fully tested by making changes, clicking save, and verifying success/error messages appear and the file is updated.

**Acceptance Scenarios**:

1. **Given** I have made changes to a policy, **When** I click "Save", **Then** the API saves the policy and I see a success message.
2. **Given** I click "Save" but the API returns an error (e.g., validation failure), **When** the error occurs, **Then** I see a clear error message explaining the problem.
3. **Given** I have unsaved changes, **When** I navigate away from the editor, **Then** I am warned about unsaved changes.

---

### User Story 7 - Preserve Unknown Fields (Priority: P1)

As a library admin, I want the editor to preserve any fields in my policy that it doesn't understand so that I don't lose custom or advanced configuration.

**Why this priority**: Critical for data integrity. Users may have extended policies or use advanced features the editor doesn't cover.

**Independent Test**: Can be fully tested by adding custom fields to a policy YAML, editing via the UI, saving, and verifying custom fields are preserved.

**Acceptance Scenarios**:

1. **Given** a policy contains fields not rendered in the editor form, **When** I save the policy through the editor, **Then** those unknown fields are preserved in the output YAML.
2. **Given** a policy contains comments in the YAML, **When** I save the policy through the editor, **Then** YAML comments are preserved where possible.

---

### Edge Cases

- What happens when a policy file has invalid YAML syntax? Display an error preventing editing until the file is manually fixed.
- How does the system handle concurrent edits to the same policy file? Use optimistic concurrency with a warning if the file changed since load.
- What happens when required fields are removed via the form? Validation prevents saving with clear error messages.
- How does the system handle very long language lists? Allow scrolling within the list component; no practical limit enforced.
- What happens if the policy file is deleted while editing? Show an error message when attempting to save.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display a form-based editor for policies accessed via the web UI.
- **FR-002**: System MUST provide controls to reorder track types in the track_order configuration.
- **FR-003**: System MUST provide controls to manage audio_language_preference as an ordered list.
- **FR-004**: System MUST provide controls to manage subtitle_language_preference as an ordered list.
- **FR-005**: System MUST provide controls to manage commentary_patterns as a list of keywords.
- **FR-006**: System MUST provide toggle controls for default_flags settings (set_first_video_default, set_preferred_audio_default, set_preferred_subtitle_default, clear_other_defaults).
- **FR-007**: System MUST display a read-only panel showing the current YAML representation of the policy.
- **FR-008**: System MUST update the YAML preview when form values change.
- **FR-009**: System MUST provide a PUT /api/policies/{name} endpoint to save policy changes.
- **FR-009a**: System MUST provide a GET /api/policies/{name} endpoint to retrieve policy data for editing (returns editable fields, raw YAML, and metadata).
- **FR-009b**: System MUST provide a GET /policies/{name}/edit endpoint to render the policy editor HTML page.
- **FR-010**: System MUST validate policy changes before saving and return clear error messages for validation failures.
- **FR-011**: System MUST preserve unknown/non-core fields in the policy file during round-trip (load → edit → save).
- **FR-012**: System MUST pre-populate the form with current policy values when opened.
- **FR-013**: System MUST show clear success/error feedback after save attempts.
- **FR-014**: System MUST warn users when navigating away with unsaved changes.
- **FR-015**: System MUST handle missing or invalid policy files gracefully with appropriate error messages.

### Key Entities

- **Policy Editor Form**: The visual interface for editing policy fields. Contains sections for track ordering, audio preferences, subtitle preferences, commentary configuration, and default flags.
- **Policy File**: A YAML file in ~/.vpo/policies/ containing the PolicySchema structure. Must be read, modified, and written with field preservation.
- **Policy Update Request**: The payload sent to PUT /api/policies/{name}. Contains modified policy fields while preserving unknown fields from the original.
- **Validation Result**: Success or failure with field-specific error messages when policy validation fails.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can modify core policy settings (track order, language preferences, default flags) without editing YAML directly.
- **SC-002**: Policy changes made through the editor are saved and take effect when policies are applied.
- **SC-003**: Unknown fields in policy files are preserved through edit operations with 100% fidelity.
- **SC-004**: Users receive clear feedback within 1 second of clicking save (success or specific error).
- **SC-005**: 90% of users can successfully modify a policy on their first attempt without external documentation.

## Assumptions

- The existing policies list view (023-policies-list-view) provides navigation to individual policy files.
- The editor is accessed via a route like /policies/{name}/edit or similar.
- YAML comment preservation is best-effort; structural comments may be preserved but inline comments may be lost depending on YAML library capabilities.
- The editor covers "core" fields as defined by the current PolicySchema: schema_version (read-only), track_order, audio_language_preference, subtitle_language_preference, commentary_patterns, default_flags, and optionally transcode/transcription settings visibility.
- Transcription policy settings (if enabled) can be edited via the form as a secondary section.
- The "audio codec priority" and "channel layout priority" mentioned in acceptance criteria refer to the transcode.audio_preserve_codecs and transcode.audio_downmix fields respectively.
- Transcode section display: The "audio codec settings" mentioned in US2 acceptance criteria refers to displaying (read-only) which codecs are preserved vs transcoded from existing transcode.audio_preserve_codecs settings. Editing transcode settings is OUT OF SCOPE for this feature and will be addressed in a future transcode editor feature.
- Form validation mirrors backend validation to catch errors before submission.
- The web UI uses vanilla JavaScript (no frameworks) consistent with existing implementation.
