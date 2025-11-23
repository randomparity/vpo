# Feature Specification: Settings/About Panel for Web UI

**Feature Branch**: `014-settings-about-panel`
**Created**: 2025-11-23
**Status**: Draft
**Input**: User description: "Add settings/about panel for Web UI"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Application Configuration (Priority: P1)

As an operator, I want to view key application configuration values from the Web UI so that I can understand the current operational context of the system without needing command-line access.

**Why this priority**: This is the core functionality of the feature - surfacing configuration information in a read-only panel is the primary user need.

**Independent Test**: Can be fully tested by navigating to the About page and verifying all configuration values are displayed accurately. Delivers immediate value by providing transparency into system configuration.

**Acceptance Scenarios**:

1. **Given** the Web UI is loaded and running, **When** the user clicks the "About" link in the navigation, **Then** the About panel is displayed with all configuration values.
2. **Given** the settings/about panel is open, **When** the user views the Backend/API base URL field, **Then** the correct URL is displayed and marked as read-only.
3. **Given** the settings/about panel is open, **When** the user views the application version field, **Then** the version number or commit hash is displayed accurately.

---

### User Story 2 - View Current Profile Information (Priority: P2)

As an operator, I want to see the current profile context (if applicable) so that I understand which configuration profile the system is operating under.

**Why this priority**: Profile information is secondary to core configuration but still important for operators managing multiple environments.

**Independent Test**: Can be tested by configuring a profile and verifying it appears in the panel, or verifying "No profile configured" appears when none is set.

**Acceptance Scenarios**:

1. **Given** the system has an active profile configured, **When** the user views the settings panel, **Then** the current profile name is displayed.
2. **Given** the system has no profile configured, **When** the user views the settings panel, **Then** an appropriate message indicates no profile is active (e.g., "Default" or "No profile configured").

---

### User Story 3 - Access Documentation Links (Priority: P3)

As an operator, I want quick access to documentation from the settings panel so that I can easily find help and reference materials.

**Why this priority**: Documentation links enhance usability but are not core functionality.

**Independent Test**: Can be tested by clicking documentation links and verifying they navigate to the correct resources.

**Acceptance Scenarios**:

1. **Given** the settings/about panel is open, **When** the user clicks a documentation link, **Then** the user is navigated to the appropriate documentation resource.
2. **Given** the settings/about panel contains documentation links, **When** the user views them, **Then** the links are clearly labeled and functional.

---

### Edge Cases

- What happens when version information is unavailable? Display "Version unavailable" or similar fallback text.
- What happens when the backend API URL cannot be determined? Display the configured or default URL with appropriate indication.
- How does the panel handle missing profile information? Show "Default" or "No profile configured" gracefully.
- What happens if the documentation URL is unreachable? Links should still be displayed; network availability is not the UI's responsibility.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display an "About" link in the Web UI navigation or header.
- **FR-002**: System MUST display the Backend/API base URL as a read-only field.
- **FR-003**: System MUST display the current profile name if one is configured.
- **FR-004**: System MUST display "Default" or equivalent when no profile is configured.
- **FR-005**: System MUST display the application version and/or git commit hash if available.
- **FR-006**: System MUST display "Version unavailable" or equivalent when version information cannot be determined.
- **FR-007**: System MUST clearly indicate that settings are read-only in this version (e.g., informational text or visual treatment).
- **FR-008**: System MUST include at least one link to documentation (e.g., project README or docs).
- **FR-009**: Navigation to the settings panel MUST integrate with the existing Web UI navigation structure.

### Key Entities

- **Configuration Display**: Represents the collection of read-only configuration values shown to the user (API URL, profile, version).
- **Documentation Link**: Represents a hyperlink to external or local documentation resources.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can access the Settings/About panel within one click from any page in the Web UI.
- **SC-002**: All required configuration fields (API URL, profile, version) are visible on the settings panel.
- **SC-003**: 100% of displayed configuration values accurately reflect the actual system configuration.
- **SC-004**: Documentation links are functional and navigate to valid resources.
- **SC-005**: The panel clearly communicates its read-only nature to users.

## Clarifications

### Session 2025-11-23

- Q: What should the navigation link/page be labeled? → A: "About" - Emphasizes read-only, informational purpose

## Assumptions

- The Web UI shell from feature 013 provides navigation infrastructure that this feature will integrate with.
- Version information can be sourced from the application package metadata or git commit information.
- Profile configuration follows existing VPO configuration patterns.
- The daemon server may optionally provide a JSON API endpoint (`/api/about`) for programmatic access; the primary delivery is server-rendered HTML.
