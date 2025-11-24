# Feature Specification: Policies List View

**Feature Branch**: `023-policies-list-view`
**Created**: 2025-11-24
**Status**: Draft
**Input**: User description: "Implement Policies list view and profile management - Add a Policies page that lists all defined policies/profiles and their basic metadata."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View All Policies (Priority: P1)

As a library admin, I want to see a list of all defined policy files so that I can understand what rules are available for my video library.

**Why this priority**: This is the core value of the feature - without a list of policies, the page has no purpose. Users need visibility into existing policies before they can manage or edit them.

**Independent Test**: Can be fully tested by navigating to /policies and verifying policy files from the configured policy directory are displayed with their names, descriptions, and key settings.

**Acceptance Scenarios**:

1. **Given** policy files exist in the configured policies directory, **When** I navigate to /policies, **Then** I see a list of all policy files with their names and descriptions.
2. **Given** a policy file has a description in its YAML, **When** I view the policies list, **Then** the description is displayed alongside the policy name.
3. **Given** no policy files exist in the policies directory, **When** I navigate to /policies, **Then** I see an empty state message explaining how to add policies.

---

### User Story 2 - View Policy Metadata (Priority: P2)

As a library admin, I want to see key metadata about each policy (last modified, schema version, key settings) so that I can quickly assess which policies are current and what they do.

**Why this priority**: Metadata provides context that helps users understand policies without opening each file. This builds on the basic list from P1.

**Independent Test**: Can be fully tested by examining policy cards/rows and verifying file modification times, schema versions, and summarized settings are displayed correctly.

**Acceptance Scenarios**:

1. **Given** a policy file exists, **When** I view the policies list, **Then** I see the file's last modified timestamp in a human-readable format.
2. **Given** a policy file has schema_version set, **When** I view the policies list, **Then** I see the schema version displayed.
3. **Given** a policy has language preferences configured, **When** I view the policies list, **Then** I see a summary of audio/subtitle language preferences (e.g., "Audio: eng, jpn | Subtitles: eng").

---

### User Story 3 - Identify Active Policy (Priority: P2)

As a library admin, I want to clearly see which policy is set as the default for the current profile so that I know which rules are currently in effect.

**Why this priority**: Knowing which policy is active is critical for understanding current behavior. Equal priority to metadata since both provide essential context.

**Independent Test**: Can be fully tested by configuring a default_policy in the active profile and verifying the policies list shows a clear visual indicator on that policy.

**Acceptance Scenarios**:

1. **Given** a profile has default_policy set to a specific policy file, **When** I view the policies list, **Then** that policy shows a clear "Default" badge or indicator.
2. **Given** no default_policy is configured for the current profile, **When** I view the policies list, **Then** no policy shows a default indicator, and I see a message indicating no default is set.
3. **Given** the default_policy points to a file that doesn't exist, **When** I view the policies list, **Then** I see a warning indicator that the configured default is missing.

---

### User Story 4 - Policy Scope Indication (Priority: P3)

As a library admin, I want to see the scope or purpose of each policy (e.g., Movies, TV, Kids) if indicated in the policy metadata so that I can quickly identify which policy applies to which content type.

**Why this priority**: Scope information is helpful but not essential for basic functionality. Many policies may not have scope metadata.

**Independent Test**: Can be fully tested by adding a scope/description field to policy files and verifying it displays on the policies list.

**Acceptance Scenarios**:

1. **Given** a policy file has a name suggesting its scope (e.g., "movies-high-quality.yaml"), **When** I view the policies list, **Then** the full filename is visible to indicate scope.
2. **Given** a policy file has transcode settings configured, **When** I view the policies list, **Then** I see an icon or badge indicating this policy includes transcoding rules.

---

### Edge Cases

- What happens when policy files have invalid YAML syntax? Display the policy with an error indicator and skip parsing details.
- What happens when the policies directory doesn't exist? Show an empty state with instructions to configure a policies directory.
- What happens when policy files are very large? Only parse metadata (first few fields) rather than full validation.
- How does the system handle concurrent policy file changes? Refresh on page load; no real-time updates required.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display a list of policy files found in the configured policies directory, sorted with the default policy first, then alphabetically by filename.
- **FR-002**: System MUST show each policy's filename and parsed description (if available).
- **FR-003**: System MUST display the last modified timestamp for each policy file.
- **FR-004**: System MUST indicate which policy is set as the default for the current profile.
- **FR-005**: System MUST show the schema_version for each successfully parsed policy.
- **FR-006**: System MUST display a summary of key settings (language preferences, transcode enabled).
- **FR-007**: System MUST handle invalid policy files gracefully by showing an error indicator without crashing.
- **FR-008**: System MUST show an appropriate empty state when no policies are found.
- **FR-009**: System MUST provide a GET /api/policies endpoint returning policy metadata as JSON.

### Key Entities

- **Policy File**: A YAML file defining video processing rules. Attributes: filename, file path, last modified time, parsed content (schema_version, audio_language_preference, subtitle_language_preference, transcode settings, transcription settings).
- **Policy Summary**: A lightweight representation of policy metadata for display. Attributes: name (filename without extension), description (from YAML or null), last_modified (ISO timestamp), schema_version, is_default (boolean), has_transcode (boolean), has_transcription (boolean), audio_languages (list), subtitle_languages (list), parse_error (string or null).
- **Profile**: The active VPO configuration profile which may specify a default_policy path.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can view all available policies within 2 seconds of navigating to the Policies page.
- **SC-002**: Users can identify which policy is the active default at a glance without additional clicks.
- **SC-003**: Invalid or malformed policy files are clearly indicated without preventing the page from loading.
- **SC-004**: The policies list accurately reflects the current state of policy files in the directory on each page load.

## Clarifications

### Session 2025-11-24

- Q: Where should the system look for policy files to list? → A: Use the fixed location ~/.vpo/policies/ (not user-configurable in this iteration)
- Q: How should the policies list handle scale? → A: No pagination; load all policies (assume <50 files typical)
- Q: How should policies be sorted in the list view? → A: Default policy first, then alphabetically

## Assumptions

- Policy files are stored in a single configured directory (not recursively scanned).
- The policies directory path is the hardcoded location ~/.vpo/policies/ (not configurable in this iteration).
- Typical installations have fewer than 50 policy files; no pagination required.
- Policy files use the .yaml or .yml extension.
- The "description" field for policies is the filename by default; a future enhancement may add an explicit description field to the policy schema.
- Scope (Movies/TV/Kids) is not currently a field in the PolicySchema; it can be inferred from filename conventions or added in a future iteration.
- "Active vs inactive" policies means: one policy can be marked as the default per profile; other policies are available but not active.
- This feature is read-only; editing policies is out of scope and will be a separate feature (visual policy editor).
