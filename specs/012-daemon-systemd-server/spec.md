# Feature Specification: Daemon Mode & Systemd-Friendly Server

**Feature Branch**: `012-daemon-systemd-server`
**Created**: 2025-11-23
**Status**: Draft
**Input**: User description: "Make vpo runnable as a long-lived background service that starts cleanly under systemd, minimizes console output, uses a robust logging system including journald-friendly behavior, and handles clean shutdown and basic health checks."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run VPO as a Background Service (Priority: P1)

As an operator, I want to run VPO as a long-lived background daemon so that it can continuously process jobs and serve API requests without manual intervention.

**Why this priority**: This is the foundational capability - without a daemon mode entrypoint, none of the other systemd integration features are possible. Operators cannot deploy VPO as a production service without this.

**Independent Test**: Can be fully tested by running `vpo serve` and verifying it starts, binds to a port, and remains running until a shutdown signal is received.

**Acceptance Scenarios**:

1. **Given** VPO is installed, **When** the operator runs `vpo serve`, **Then** the daemon starts, initializes the database connection, binds to the configured port, and runs until receiving a shutdown signal.
2. **Given** the database is unreachable, **When** the operator runs `vpo serve`, **Then** the daemon logs a clear error message and exits with a non-zero exit code.
3. **Given** the configured port is already in use, **When** the operator runs `vpo serve`, **Then** the daemon logs a clear error message and exits with a non-zero exit code.
4. **Given** the daemon is running, **When** the operator sends SIGTERM, **Then** the daemon gracefully shuts down (stops accepting new work, completes or cancels in-flight tasks, flushes logs, closes connections) within 30 seconds.

---

### User Story 2 - Deploy VPO via Systemd (Priority: P2)

As an operator, I want to deploy VPO as a systemd-managed service so that it starts automatically on boot, restarts on failure, and integrates with standard Linux service management tools.

**Why this priority**: Systemd is the primary process manager for production Linux deployments. This enables operators to deploy VPO using familiar tools and patterns.

**Independent Test**: Can be tested by installing the example systemd unit file, running `systemctl start vpo`, and verifying the service is running via `systemctl status vpo` and logs appear in `journalctl -u vpo`.

**Acceptance Scenarios**:

1. **Given** the systemd unit file is installed, **When** the operator runs `systemctl start vpo`, **Then** the daemon starts and becomes accessible.
2. **Given** the daemon is running under systemd, **When** the operator runs `systemctl stop vpo`, **Then** systemd sends SIGTERM and the daemon shuts down gracefully.
3. **Given** the daemon crashes, **When** the restart policy is `on-failure`, **Then** systemd automatically restarts the daemon.
4. **Given** the daemon is running, **When** the operator runs `journalctl -u vpo`, **Then** all daemon logs are visible with proper timestamps and log levels.

---

### User Story 3 - Configure Daemon Settings (Priority: P3)

As an operator, I want to configure daemon settings (bind address, port, logging) via a config file and CLI flags so that I can customize the deployment without modifying code.

**Why this priority**: Production deployments require configuration flexibility. Config files enable fleet-wide consistency while CLI flags allow per-instance overrides.

**Independent Test**: Can be tested by creating a config file with custom settings, running `vpo serve`, and verifying the daemon uses those settings. Then override with CLI flags and verify the override takes precedence.

**Acceptance Scenarios**:

1. **Given** a config file at `~/.vpo/config.toml` with `server.port = 9000`, **When** the operator runs `vpo serve`, **Then** the daemon binds to port 9000.
2. **Given** a config file with `server.port = 9000`, **When** the operator runs `vpo serve --port 8080`, **Then** the daemon binds to port 8080 (CLI overrides config).
3. **Given** a malformed config file, **When** the operator runs `vpo serve`, **Then** the daemon logs a clear error message and exits with a non-zero exit code.
4. **Given** no config file exists, **When** the operator runs `vpo serve`, **Then** the daemon uses sensible defaults and starts successfully.

---

### User Story 4 - Monitor Daemon Health (Priority: P3)

As an operator, I want a health-check endpoint so that external monitoring systems can verify the daemon is responsive and its dependencies are healthy.

**Why this priority**: Health checks are essential for production monitoring but are not required for basic daemon functionality.

**Independent Test**: Can be tested by starting the daemon, sending `GET /health`, and verifying a 200 response when healthy and appropriate error codes when dependencies are unavailable.

**Acceptance Scenarios**:

1. **Given** the daemon is running and healthy, **When** a client sends `GET /health`, **Then** the response is HTTP 200 with status information.
2. **Given** the daemon is running but the database is unreachable, **When** a client sends `GET /health`, **Then** the response is HTTP 503 indicating degraded status.
3. **Given** the daemon has not completed startup, **When** a client sends `GET /health`, **Then** the response indicates the service is not ready.

---

### User Story 5 - Structured Logging for Observability (Priority: P4)

As an operator, I want structured (JSON) logging so that logs integrate well with log aggregation and analysis tools.

**Why this priority**: Structured logging improves observability but plain-text logging is sufficient for basic deployments.

**Independent Test**: Can be tested by configuring `log_format: json`, starting the daemon, and verifying log output is valid JSON with expected fields.

**Acceptance Scenarios**:

1. **Given** `log_format: json` in config, **When** the daemon logs a message, **Then** the output is a valid JSON object with timestamp, level, logger, and message fields.
2. **Given** `log_format: text` in config (default), **When** the daemon logs a message, **Then** the output is human-readable text with timestamp and level.
3. **Given** structured logging is enabled, **When** a log message has context (job_id, file_path), **Then** the JSON includes those fields.

---

### Edge Cases

- What happens when the daemon receives SIGKILL during shutdown? (Resources may leak; this is expected - systemd uses SIGKILL as last resort after timeout)
- How does the system handle rapid consecutive SIGTERM signals? (Treat as single shutdown request)
- What happens when the daemon cannot write to the log destination? (Log error to stderr, continue operating if possible)
- How does the system handle config file permissions errors? (Log clear error, exit with non-zero code)
- What happens when the health endpoint is called during graceful shutdown? (Return 503 indicating shutdown in progress)

## Requirements *(mandatory)*

### Functional Requirements

**Daemon Lifecycle**
- **FR-001**: System MUST provide a `vpo serve` CLI command that runs the daemon in foreground mode
- **FR-002**: Daemon MUST initialize database connections at startup and verify connectivity
- **FR-003**: Daemon MUST bind to a configurable network address and port
- **FR-004**: Daemon MUST run continuously until receiving a shutdown signal
- **FR-005**: Daemon MUST NOT use interactive prompts, TTY detection, or console spinners

**Signal Handling**
- **FR-006**: Daemon MUST respond to SIGTERM by initiating graceful shutdown
- **FR-007**: Daemon MUST respond to SIGINT by initiating graceful shutdown (same as SIGTERM)
- **FR-008**: Graceful shutdown MUST stop accepting new work
- **FR-009**: Graceful shutdown MUST wait for in-flight tasks to complete up to the shutdown timeout, then cancel any remaining tasks
- **FR-010**: Graceful shutdown MUST flush all log buffers before exit
- **FR-011**: Graceful shutdown MUST close all database connections
- **FR-012**: Graceful shutdown MUST complete within a configurable timeout (default: 30 seconds)

**Logging**
- **FR-013**: System MUST provide centralized logging configuration for all components
- **FR-014**: Logging MUST support configurable log levels (debug, info, warning, error)
- **FR-015**: Logging MUST support plain-text format (default)
- **FR-016**: Logging MUST support structured JSON format (opt-in)
- **FR-017**: In daemon mode, all operational messages MUST go through the logging framework (no direct stdout/stderr prints)
- **FR-018**: Log output MUST go to stderr by default (for journald compatibility)
- **FR-019**: Log messages MUST include timestamp, level, logger name, and message
- **FR-020**: Structured logs SHOULD include context fields (job_id, file_path) when available

**Configuration**
- **FR-021**: System MUST support configuration via TOML config file at `~/.vpo/config.toml`
- **FR-022**: System MUST support custom config file path via `--config` flag
- **FR-023**: CLI flags MUST override config file settings
- **FR-024**: Config file MUST override environment defaults
- **FR-025**: System MUST support these server settings: bind address, port, log level, log format
- **FR-026**: Config loading errors MUST be logged clearly and cause non-zero exit

**Health Check**
- **FR-027**: System MUST provide a `GET /health` endpoint
- **FR-028**: Health endpoint MUST return HTTP 200 when process is running and database is reachable
- **FR-029**: Health endpoint MUST return HTTP 503 when critical dependencies are unavailable
- **FR-030**: Health endpoint MUST be fast (under 100ms) and side-effect free

**CLI Interface**
- **FR-031**: `vpo serve` MUST accept `--bind` flag for host address
- **FR-032**: `vpo serve` MUST accept `--port` flag for port number
- **FR-033**: `vpo serve` MUST accept `--log-level` flag (debug/info/warning/error)
- **FR-034**: `vpo serve` MUST accept `--log-format` flag (text/json)
- **FR-035**: `vpo serve --help` MUST document all daemon-related options

**Error Handling**
- **FR-036**: Startup failures MUST exit with non-zero exit code
- **FR-037**: Startup failures MUST log a clear error message
- **FR-038**: Stack traces MUST only be shown in debug mode

### Key Entities

- **ServerConfig**: Configuration for daemon mode - bind address, port, log level, log format, shutdown timeout
- **HealthStatus**: Result of health check - overall status, database connectivity, migration status, uptime
- **ShutdownState**: Tracks shutdown progress - initiated timestamp, tasks remaining, timeout deadline

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Operator can start VPO as a background daemon that runs continuously without manual intervention
- **SC-002**: Daemon gracefully shuts down within 30 seconds when receiving SIGTERM
- **SC-003**: Daemon can be managed via systemd using standard commands (start, stop, restart, status)
- **SC-004**: All daemon logs appear in journald when running under systemd
- **SC-005**: Health endpoint responds within 100ms and accurately reflects system state
- **SC-006**: Configuration changes via config file take effect on daemon restart
- **SC-007**: CLI flags successfully override config file settings
- **SC-008**: Daemon startup failures produce clear error messages and non-zero exit codes
- **SC-009**: No console output (banners, spinners, progress bars) appears when running in daemon mode
- **SC-010**: Structured JSON logs are valid and parseable by standard tools when JSON format is enabled

## Clarifications

### Session 2025-11-23

- Q: What is the in-flight task shutdown policy? → A: Wait for in-flight tasks to complete up to the shutdown timeout, then cancel any remaining tasks.
- Q: What is the default server port? → A: 8321 (distinctive, unlikely to conflict with other services).

## Assumptions

- VPO already has or will have a Web API component that the daemon will serve (the existing architecture mentions API/job-scheduler components)
- The existing SQLite database at `~/.vpo/library.db` will be used by the daemon
- Systemd is the target service manager; other init systems (SysV, OpenRC) are not in scope
- SIGHUP for config reload is deferred to a future sprint (noted in original description)
- The daemon runs in foreground mode (systemd handles backgrounding via Type=simple)
- Default bind address is `127.0.0.1` (localhost only) for security; operators can configure for network access
- Default port is 8321 (distinctive, unlikely to conflict with other services)
