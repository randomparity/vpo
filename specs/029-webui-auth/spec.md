# Feature Specification: Web UI Authentication

**Feature Branch**: `029-webui-auth`
**Created**: 2025-11-25
**Status**: Draft
**Input**: User description: "Add minimal authentication/authorization for Web UI - implement a minimal access control mechanism for the Web UI and API, sufficient to avoid completely open access."

## Clarifications

### Session 2025-11-25

- Q: Should the auth token be configurable via environment variable in addition to config file? → A: Environment variable takes precedence over config file.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operator Protects Web UI With Token (Priority: P1)

An operator deploying VPO wants to prevent unauthorized access to the Web UI and API. They configure a shared secret token in the server configuration file. When the server starts, all API and UI requests require this token to be present. Without valid credentials, access is denied with an appropriate error.

**Why this priority**: This is the core value of the feature - providing a basic access barrier. Without this, the Web UI remains completely open to anyone who can reach the network port.

**Independent Test**: Can be fully tested by configuring a token, starting the server, and verifying that requests without the token are rejected while requests with the token succeed.

**Acceptance Scenarios**:

1. **Given** a VPO server configured with an authentication token, **When** a user attempts to access the Web UI without credentials, **Then** they receive a 401 Unauthorized response.
2. **Given** a VPO server configured with an authentication token, **When** a user provides the correct token via HTTP header or browser auth dialog, **Then** they gain access to the Web UI.
3. **Given** a VPO server configured with an authentication token, **When** a user provides an incorrect token, **Then** they receive a 401 Unauthorized response.

---

### User Story 2 - Operator Runs Without Auth (Priority: P2)

An operator running VPO in a secure environment (localhost-only, behind VPN, etc.) wants to skip authentication setup. When no auth token is configured, the server operates without authentication, preserving backward compatibility. The server logs a warning about unauthenticated access.

**Why this priority**: Backward compatibility and ease of getting started are important, but secondary to the core security feature.

**Independent Test**: Can be fully tested by starting the server without auth configuration and verifying all endpoints remain accessible, with a warning logged.

**Acceptance Scenarios**:

1. **Given** a VPO server with no authentication configured, **When** the server starts, **Then** all endpoints remain accessible without credentials.
2. **Given** a VPO server with no authentication configured, **When** the server starts, **Then** a warning is logged indicating the server is running without authentication.

---

### User Story 3 - Browser-Based Authentication (Priority: P3)

A user accessing the Web UI through a browser should be able to authenticate conveniently. The system supports HTTP Basic Authentication, which browsers handle natively via the built-in login dialog. After authenticating once, subsequent requests include the credentials automatically.

**Why this priority**: Browser UX is important but depends on the core auth mechanism being in place first.

**Independent Test**: Can be fully tested by opening the Web UI in a browser, being prompted for credentials, entering them, and verifying continued access without re-prompting.

**Acceptance Scenarios**:

1. **Given** a browser user accessing a protected VPO Web UI, **When** they navigate to any page, **Then** the browser displays a username/password dialog.
2. **Given** a browser user who has entered valid credentials, **When** they navigate to other pages in the same session, **Then** they are not prompted again.
3. **Given** a browser user who enters invalid credentials, **When** the dialog is submitted, **Then** the browser re-prompts for credentials.

---

### Edge Cases

- What happens when the auth token contains special characters? The system must handle any printable ASCII string as a valid token.
- How does the system handle empty or whitespace-only tokens? Empty tokens are treated as "no authentication configured" to prevent accidental lockout with invalid config.
- What happens during authentication failures under high load? The system responds with 401 status within the <100ms latency budget defined in SC-003.
- How are health check endpoints handled? The `/health` endpoint remains unauthenticated to support load balancer health checks and monitoring systems.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support HTTP Basic Authentication for protecting the Web UI and API endpoints.
- **FR-002**: System MUST allow configuration of a shared secret token via environment variable (VPO_AUTH_TOKEN) or server configuration file, with environment variable taking precedence.
- **FR-003**: System MUST return HTTP 401 Unauthorized status when valid credentials are not provided to a protected endpoint.
- **FR-004**: System MUST include a `WWW-Authenticate: Basic realm="VPO"` header in 401 responses to trigger browser authentication dialogs.
- **FR-005**: System MUST allow the `/health` endpoint to remain unauthenticated to support monitoring and health checks.
- **FR-006**: System MUST operate without authentication when no auth token is configured (backward compatibility).
- **FR-007**: System MUST log a warning at startup when running without authentication configured.
- **FR-008**: System MUST accept credentials via the `Authorization: Basic <credentials>` HTTP header.
- **FR-009**: System MUST use constant-time comparison for token validation to prevent timing attacks.
- **FR-010**: System MUST document that this authentication mechanism is minimal and not recommended for production use without additional security measures.

### Key Entities

- **AuthToken**: A shared secret string configured by the operator. Used as the password in HTTP Basic Authentication. The username is ignored (any username is accepted).
- **ServerConfig**: Extended to include an optional `auth_token` field for storing the configured secret.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of API and UI requests (except `/health`) are rejected with 401 status when auth is configured but credentials are not provided.
- **SC-002**: Users can authenticate and access all protected features within 30 seconds of first visiting the Web UI (including reading password from config and entering it).
- **SC-003**: Server startup time increases by less than 100 milliseconds when auth is enabled.
- **SC-004**: Authentication works correctly in all major browsers (Chrome, Firefox, Safari, Edge) using their native Basic Auth dialogs.
- **SC-005**: Zero regression in existing functionality when authentication is disabled (default backward-compatible mode).

## Assumptions

- The operator has a secure method for storing and retrieving the authentication token (e.g., environment variable, secure config file permissions).
- The VPO server is typically deployed behind HTTPS termination (reverse proxy) or on localhost, so Basic Auth credentials are transmitted over an encrypted channel.
- A single shared token is sufficient for this sprint's requirements; per-user authentication is out of scope.
- The username field in Basic Auth is not validated - only the password (token) matters. This simplifies configuration while maintaining security.

## Non-Goals (Out of Scope)

- Per-user accounts or role-based access control
- OAuth2, OIDC, or external identity provider integration
- Session management or remember-me functionality beyond browser Basic Auth caching
- API key management UI
- Rate limiting for failed authentication attempts
- Audit logging of authentication events (beyond standard access logs)
