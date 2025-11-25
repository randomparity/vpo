# Feature Specification: Policy Validation and Error Reporting

**Feature Branch**: `025-policy-validation`
**Created**: 2025-11-25
**Status**: Draft
**Input**: User description: "Add policy validation and error reporting in Web UI - Connect policy saving to backend validation and surface errors clearly in the UI."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Save Policy with Successful Validation (Priority: P1)

As a library admin, I want to save my policy changes and see clear confirmation that the policy is valid so that I have confidence my configuration will work correctly.

**Why this priority**: This is the happy-path core functionality. Users need to know their changes are valid and saved before anything else matters.

**Independent Test**: Can be fully tested by making valid changes in the policy editor, clicking save, and verifying success feedback is displayed with a summary of what changed.

**Acceptance Scenarios**:

1. **Given** I have made valid changes to a policy (e.g., reordered audio languages), **When** I click "Save Changes", **Then** the backend validates the policy, saves it, and the UI shows a success message.
2. **Given** I have saved a policy successfully, **When** I view the success message, **Then** I see a brief summary of what was changed (e.g., "Updated audio_language_preference").
3. **Given** the policy saves successfully, **When** I view the save feedback, **Then** the feedback appears within 1 second of clicking save.

---

### User Story 2 - Save Policy with Validation Errors (Priority: P1)

As a library admin, I want to see clear, actionable error messages when my policy configuration is invalid so that I can fix the problems without guessing.

**Why this priority**: Equal priority with success case. Users need immediate, clear feedback when something goes wrong to avoid frustration and broken workflows.

**Independent Test**: Can be fully tested by entering invalid data (e.g., invalid language code, empty required list), clicking save, and verifying specific error messages appear associated with the relevant fields.

**Acceptance Scenarios**:

1. **Given** I have entered an invalid language code (e.g., "english" instead of "eng"), **When** I click "Save Changes", **Then** the UI shows an error message specifically mentioning the invalid language code.
2. **Given** I have removed all items from a required list (e.g., audio_language_preference), **When** I click "Save Changes", **Then** the UI shows an error message indicating the list cannot be empty.
3. **Given** I have entered an invalid regex pattern in commentary_patterns, **When** I click "Save Changes", **Then** the UI shows an error message indicating which pattern is invalid and why.
4. **Given** a validation error occurs, **When** the error is displayed, **Then** the error is associated with the specific field that has the problem (field-level error).
5. **Given** a validation error occurs, **When** I view the error, **Then** the policy is NOT saved/persisted (save is blocked until errors are fixed).

---

### User Story 3 - Test Policy Without Saving (Priority: P2)

As a cautious library admin, I want to validate my policy configuration without actually saving it so that I can check my changes are correct before committing them.

**Why this priority**: This is a safety feature for users who want to verify before committing. Important but secondary to basic save functionality.

**Independent Test**: Can be fully tested by making changes, clicking "Test Policy" button, and verifying validation feedback appears without the policy file being modified.

**Acceptance Scenarios**:

1. **Given** I have made changes to a policy, **When** I click "Test Policy", **Then** the backend validates the policy and returns validation results without saving.
2. **Given** I click "Test Policy" with valid configuration, **When** validation completes, **Then** I see a success message indicating "Policy configuration is valid".
3. **Given** I click "Test Policy" with invalid configuration, **When** validation completes, **Then** I see the same detailed error messages as I would from a save attempt.
4. **Given** I have clicked "Test Policy" and seen validation results, **When** I check the policy file on disk, **Then** the file has NOT been modified.

---

### User Story 4 - Real-time Field Validation (Priority: P2)

As a library admin, I want immediate feedback as I enter data in form fields so that I can catch errors before attempting to save.

**Why this priority**: Improves user experience by catching errors early, but save-time validation is the safety net.

**Independent Test**: Can be fully tested by typing in form fields and verifying validation indicators appear without clicking any buttons.

**Acceptance Scenarios**:

1. **Given** I am typing a language code in the audio language input, **When** I enter an invalid format (e.g., "12345"), **Then** the input shows a visual invalid indicator (red border) immediately.
2. **Given** I am typing a valid language code, **When** I complete a valid 2-3 letter code (e.g., "jpn"), **Then** the input shows a visual valid indicator.
3. **Given** I am typing a commentary pattern, **When** I enter an invalid regex (e.g., unclosed bracket "[abc"), **Then** the input shows a visual invalid indicator.

---

### User Story 5 - View Diff Summary on Successful Save (Priority: P3)

As a library admin, I want to see a summary of what changed when I save a policy so that I can confirm my intended changes were applied.

**Why this priority**: Nice-to-have enhancement that builds user confidence but not critical for basic validation flow.

**Independent Test**: Can be fully tested by making specific changes, saving, and verifying the diff summary accurately reflects the changes made.

**Acceptance Scenarios**:

1. **Given** I have changed the audio_language_preference from [eng, jpn] to [jpn, eng], **When** I save successfully, **Then** the success message includes "audio_language_preference: order changed".
2. **Given** I have added a new commentary pattern, **When** I save successfully, **Then** the success message includes "commentary_patterns: added 1 pattern".
3. **Given** I have changed multiple fields, **When** I save successfully, **Then** the diff summary lists all changed fields.

---

### Edge Cases

- What happens when the backend returns an unexpected error format? Display a generic error message with the raw error text.
- What happens when network connectivity is lost during save? Display a network error message prompting the user to check connectivity and try again.
- What happens when validation errors span multiple fields? Display all errors, not just the first one.
- What happens when concurrent modification is detected? Display the existing "Concurrent modification detected" message (already implemented).
- What happens when the user tries to save with no changes? The save button remains disabled (already implemented).
- What happens when real-time validation differs from server validation? Server validation is authoritative; real-time validation is advisory.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST validate policy data against PolicyModel schema before persisting changes.
- **FR-002**: System MUST return field-level validation errors in a structured format (field path + error message).
- **FR-003**: System MUST prevent policy persistence when validation fails.
- **FR-004**: UI MUST display validation errors with clear association to the problematic field.
- **FR-005**: UI MUST display a success message with diff summary when policy saves successfully.
- **FR-006**: System MUST provide a "Test Policy" endpoint that validates without saving.
- **FR-007**: UI MUST provide a "Test Policy" button that triggers validation without saving.
- **FR-008**: UI MUST provide real-time validation feedback for language code and regex pattern inputs.
- **FR-009**: UI MUST scroll to and focus the first error when validation fails.
- **FR-010**: System MUST return validation feedback within 1 second of request.

### Key Entities

- **ValidationError**: Represents a single validation error. Contains field path (e.g., "audio_language_preference[0]"), error message, and optional error code.
- **ValidationResult**: Represents the complete validation outcome. Contains success status, list of ValidationErrors (if any), and validated policy data (if successful).
- **DiffSummary**: Represents changes between original and updated policy. Contains list of changed field names and brief description of each change type.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users receive validation feedback within 1 second of clicking Save or Test Policy.
- **SC-002**: 100% of validation errors include the specific field path and a human-readable message.
- **SC-003**: Users can identify and fix validation errors without needing to consult documentation.
- **SC-004**: Users can verify policy validity without modifying the policy file via Test Policy feature.
- **SC-005**: 95% of users can successfully identify which field caused a validation error on first view.

## Assumptions

- The existing PolicyModel (Pydantic) validation provides comprehensive field-level error information via ValidationError.errors().
- The existing policy editor JavaScript already has infrastructure for showing errors (validationErrors element, showError function).
- The "Test Policy" button will be placed near the existing "Save Changes" button for discoverability.
- Real-time validation in the browser is advisory only; server-side validation is authoritative and may catch additional errors.
- The diff summary will show field names in user-friendly format (not raw internal names).
- CSRF protection will apply to the new Test Policy endpoint (POST method).
- Error response format: `{"success": false, "errors": [{"field": "path", "message": "text"}], "details": "optional general message"}`.
- Success response format: `{"success": true, "changed_fields": ["field1", "field2"], "policy": {...}}`.
