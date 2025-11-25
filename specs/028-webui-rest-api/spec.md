# Feature Specification: Web UI REST API Endpoints

**Feature Branch**: `028-webui-rest-api`
**Created**: 2025-11-25
**Status**: Draft
**Input**: User description: "Expose Web UI REST API endpoints"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Frontend Fetches Resource Lists (Priority: P1)

A WebUI developer builds a dashboard that displays lists of jobs, library files, policies, plans, and transcriptions. The frontend needs to fetch paginated, filtered data from the backend to populate tables and lists.

**Why this priority**: Core functionality - without list endpoints, the frontend cannot display any data to users. This is the foundation for all other UI features.

**Independent Test**: Can be tested by making HTTP requests to list endpoints and verifying JSON responses contain expected fields, pagination metadata, and filter behavior.

**Acceptance Scenarios**:

1. **Given** the API is running, **When** a GET request is made to `/api/jobs` with no filters, **Then** a JSON response is returned containing a `jobs` array, `total` count, `limit`, `offset`, and `has_filters` boolean
2. **Given** the API is running, **When** a GET request is made to `/api/library?status=ok&limit=10&offset=0`, **Then** only files with status "ok" are returned, limited to 10 results
3. **Given** the API is running, **When** a GET request is made to `/api/policies`, **Then** a JSON response is returned containing policy metadata including name, filename, last_modified, and feature flags

---

### User Story 2 - Frontend Fetches Resource Details (Priority: P1)

A WebUI developer builds detail views that display comprehensive information about a single job, file, transcription, policy, or plan. The frontend needs to fetch all relevant data for a specific resource by ID.

**Why this priority**: Essential for drill-down functionality - users need to view details after seeing items in lists.

**Independent Test**: Can be tested by making HTTP requests to detail endpoints with valid IDs and verifying complete resource data is returned.

**Acceptance Scenarios**:

1. **Given** a job exists with ID "550e8400-e29b-41d4-a716-446655440000", **When** a GET request is made to `/api/jobs/550e8400-e29b-41d4-a716-446655440000`, **Then** complete job details are returned including status, progress, timestamps, and summary
2. **Given** a file exists with ID "42", **When** a GET request is made to `/api/library/42`, **Then** complete file details are returned including track information, metadata, and transcription status
3. **Given** a resource does not exist, **When** a GET request is made to its detail endpoint, **Then** a 404 response is returned with an error message

---

### User Story 3 - Frontend Modifies Policies (Priority: P2)

A WebUI developer implements a policy editor that allows users to view and save policy configurations. The frontend needs to load current policy data, validate changes, and save updates.

**Why this priority**: Write operations enable user workflow completion but depend on read operations being functional first.

**Independent Test**: Can be tested by loading a policy, modifying it via PUT request, and verifying the changes persist.

**Acceptance Scenarios**:

1. **Given** a policy named "default" exists, **When** a PUT request is made to `/api/policies/default` with valid policy data, **Then** the policy is updated and the response includes the updated data and new timestamp
2. **Given** invalid policy data is submitted, **When** a PUT request is made with validation errors, **Then** a 400 response is returned with structured error details including field names and error codes
3. **Given** a policy was modified by another user, **When** a PUT request is made with a stale timestamp, **Then** a 409 Conflict response is returned indicating concurrent modification

---

### User Story 4 - Frontend Approves/Rejects Plans (Priority: P2)

A WebUI developer implements plan approval workflow. The frontend needs to submit approve or reject actions for pending plans and receive confirmation with next steps.

**Why this priority**: Enables the core approval workflow but depends on plans list being functional first.

**Independent Test**: Can be tested by creating a pending plan, approving/rejecting it via POST, and verifying state transition.

**Acceptance Scenarios**:

1. **Given** a pending plan exists, **When** a POST request is made to `/api/plans/{id}/approve`, **Then** the plan status changes to "approved", an execution job is created, and the response includes the job ID and URL
2. **Given** a pending plan exists, **When** a POST request is made to `/api/plans/{id}/reject`, **Then** the plan status changes to "rejected" and the response confirms the action
3. **Given** a plan is not in "pending" status, **When** an approve/reject request is made, **Then** a 409 Conflict response is returned indicating invalid state transition

---

### User Story 5 - API Reference Documentation (Priority: P3)

A WebUI developer needs documentation describing all available endpoints, their parameters, and response formats to build frontend features correctly.

**Why this priority**: Documentation supports development but doesn't block core functionality.

**Independent Test**: Can be tested by verifying documentation file exists and covers all implemented endpoints with examples.

**Acceptance Scenarios**:

1. **Given** the API is implemented, **When** a developer reads the API reference, **Then** all endpoints are documented with HTTP methods, paths, parameters, and response schemas
2. **Given** the API reference exists, **When** a developer follows the documented examples, **Then** the actual API behavior matches the documentation

---

### Edge Cases

- What happens when requesting a resource with an invalid ID format (e.g., non-UUID for jobs, non-integer for files)?
  - Return 400 Bad Request with clear error message
- How does the system handle requests during server shutdown?
  - Return 503 Service Unavailable with "Service is shutting down" message
- What happens when the database connection is unavailable?
  - Return 503 Service Unavailable with "Database not available" message
- How are pagination parameters validated?
  - Limit clamped to 1-100 range, offset must be non-negative, invalid values use defaults
- What happens when filter parameters have invalid values?
  - Return 400 Bad Request identifying the invalid parameter value

## Requirements *(mandatory)*

### Functional Requirements

**Jobs Endpoints:**
- **FR-001**: System MUST provide `GET /api/jobs` endpoint returning paginated job listings with filter support (status, type, since)
- **FR-002**: System MUST provide `GET /api/jobs/{id}` endpoint returning complete job details including logs availability and summary
- **FR-002a**: System MUST provide `GET /api/jobs/{id}/logs` endpoint returning paginated log lines for a job
- **FR-002b**: System MUST provide `GET /api/jobs/{id}/errors` endpoint returning scan errors for scan-type jobs

**Library Endpoints:**
- **FR-003**: System MUST provide `GET /api/library` endpoint returning paginated file listings with filter support (status, search, resolution, audio_lang, subtitles)
- **FR-003a**: System MUST provide `GET /api/library/languages` endpoint returning available audio language codes for filter population
- **FR-004**: System MUST provide `GET /api/library/{id}` endpoint returning complete file details including track information

**Transcriptions Endpoints:**
- **FR-005**: System MUST provide `GET /api/transcriptions` endpoint returning paginated transcription listings with filter support (show_all to include files without transcriptions)
- **FR-006**: System MUST provide `GET /api/transcriptions/{id}` endpoint returning complete transcription details including transcript sample and classification

**Policies Endpoints:**
- **FR-007**: System MUST provide `GET /api/policies` endpoint returning all discovered policy files with metadata
- **FR-008**: System MUST provide `GET /api/policies/{name}` endpoint returning complete policy configuration
- **FR-009**: System MUST provide `PUT /api/policies/{name}` endpoint for updating policy configurations with validation
- **FR-010**: System MUST provide `POST /api/policies/{name}/validate` endpoint for dry-run validation without saving

**Plans Endpoints:**
- **FR-011**: System MUST provide `GET /api/plans` endpoint returning paginated plan listings with filter support (status, since, policy_name)
- **FR-012**: System MUST provide `POST /api/plans/{id}/approve` endpoint that transitions plan to approved status and creates execution job
- **FR-013**: System MUST provide `POST /api/plans/{id}/reject` endpoint that transitions plan to rejected status

**Cross-Cutting Requirements:**
- **FR-014**: All endpoints MUST return JSON responses with consistent structure
- **FR-015**: All list endpoints MUST support pagination via `limit` and `offset` parameters
- **FR-016**: All endpoints MUST return appropriate HTTP status codes (200, 400, 404, 409, 503)
- **FR-017**: All modifying endpoints (PUT, POST) MUST validate input and return structured errors
- **FR-018**: System MUST provide API reference documentation in `docs/api-webui.md`

### Key Entities

- **Job**: Background task with id (UUID), type, status, file_path, progress, timestamps, summary
- **File**: Media file with id (integer), path, filename, tracks, scan status, metadata
- **Transcription**: Audio transcription result with id, track_id, detected_language, confidence, transcript_sample
- **Policy**: YAML policy configuration with name, track_order, language preferences, feature flags
- **Plan**: Pending action plan with id (UUID), file_id, policy_name, actions, status

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Frontend developers can load any resource list within 1 second under normal load
- **SC-002**: Frontend developers can load any resource detail within 500ms under normal load
- **SC-003**: All API responses include consistent error structures that enable frontend error handling
- **SC-004**: Policy save operations provide clear feedback on success, validation errors, or conflicts
- **SC-005**: Plan approve/reject operations complete successfully with proper state transitions 95% of attempts
- **SC-006**: API documentation covers 100% of implemented endpoints with request/response examples
- **SC-007**: Frontend developers can implement all required UI features using only documented API endpoints

## Assumptions

- The API serves a same-origin frontend (no CORS configuration needed for production deployment)
- Authentication will be added in a future feature; current implementation assumes trusted local network access
- All datetime values are stored and returned in UTC ISO-8601 format
- The existing route registration pattern in `setup_ui_routes()` will be preserved
- Response schemas follow existing patterns established by `JobListResponse`, `FileListResponse`, etc.
