# Data Model: Daemon Mode & Systemd-Friendly Server

**Feature**: 012-daemon-systemd-server
**Date**: 2025-11-23

## Overview

This feature introduces configuration and runtime state models for daemon mode. No database schema changes are required - the daemon uses the existing schema v7 for health checks.

## Configuration Models

### ServerConfig

**Purpose**: Configuration for the daemon server component

**Location**: `src/vpo/config/models.py`

```python
@dataclass
class ServerConfig:
    """Configuration for daemon server mode."""

    bind: str = "127.0.0.1"
    """Network address to bind to. Default localhost for security."""

    port: int = 8321
    """Port number for HTTP server. Default 8321 (distinctive, avoids conflicts)."""

    shutdown_timeout: float = 30.0
    """Seconds to wait for graceful shutdown before cancelling tasks."""
```

**TOML Configuration**:
```toml
[server]
bind = "127.0.0.1"
port = 8321
shutdown_timeout = 30
```

**Environment Variables**:
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VPO_SERVER_BIND` | str | "127.0.0.1" | Network bind address |
| `VPO_SERVER_PORT` | int | 8321 | HTTP server port |
| `VPO_SERVER_SHUTDOWN_TIMEOUT` | float | 30.0 | Shutdown timeout seconds |

**CLI Flag Overrides**:
| Flag | Maps To |
|------|---------|
| `--bind` | `server.bind` |
| `--port` | `server.port` |

### VPOConfig Extension

**Change**: Add `server: ServerConfig` field to existing `VPOConfig` dataclass

```python
@dataclass
class VPOConfig:
    tools: ToolPathsConfig
    detection: DetectionConfig
    behavior: BehaviorConfig
    plugins: PluginConfig
    jobs: JobsConfig
    worker: WorkerConfig
    logging: LoggingConfig
    transcription: TranscriptionPluginConfig
    server: ServerConfig  # NEW
```

## Runtime State Models

### HealthStatus

**Purpose**: Response payload for health check endpoint

**Location**: `src/vpo/server/app.py`

```python
@dataclass
class HealthStatus:
    """Health check response payload."""

    status: str
    """Overall status: 'healthy', 'degraded', or 'unhealthy'."""

    database: str
    """Database connectivity: 'connected' or 'disconnected'."""

    uptime_seconds: float
    """Seconds since daemon startup."""

    version: str
    """VPO version string."""

    shutting_down: bool = False
    """True if graceful shutdown is in progress."""
```

**Serialization** (JSON response):
```json
{
  "status": "healthy",
  "database": "connected",
  "uptime_seconds": 3661.5,
  "version": "0.1.0",
  "shutting_down": false
}
```

**Status Determination Logic**:
| Condition | Status | HTTP Code |
|-----------|--------|-----------|
| Database connected, not shutting down | "healthy" | 200 |
| Database disconnected, not shutting down | "degraded" | 503 |
| Shutting down (any database state) | "unhealthy" | 503 |

### ShutdownState

**Purpose**: Coordinate graceful shutdown across components

**Location**: `src/vpo/server/lifecycle.py`

```python
@dataclass
class ShutdownState:
    """Tracks shutdown progress for graceful termination."""

    initiated: datetime | None = None
    """UTC timestamp when shutdown was initiated, None if not shutting down."""

    timeout_deadline: datetime | None = None
    """UTC timestamp after which remaining tasks will be cancelled."""

    tasks_remaining: int = 0
    """Count of in-flight tasks awaiting completion."""

    @property
    def is_shutting_down(self) -> bool:
        """Returns True if shutdown has been initiated."""
        return self.initiated is not None

    @property
    def is_timed_out(self) -> bool:
        """Returns True if shutdown timeout has been exceeded."""
        if self.timeout_deadline is None:
            return False
        return datetime.now(UTC) >= self.timeout_deadline
```

## State Transitions

### Daemon Lifecycle States

```
┌─────────────┐
│   STARTING  │ ← vpo serve invoked
└──────┬──────┘
       │ Config loaded, logging configured
       ▼
┌─────────────┐
│  CONNECTING │ ← Verify database, bind port
└──────┬──────┘
       │ All checks pass
       ▼
┌─────────────┐
│   RUNNING   │ ← Serving requests, health=200
└──────┬──────┘
       │ SIGTERM/SIGINT received
       ▼
┌─────────────┐
│ SHUTTING    │ ← health=503, stop accepting work
│    DOWN     │   Wait for in-flight tasks
└──────┬──────┘
       │ Tasks complete OR timeout
       ▼
┌─────────────┐
│   STOPPED   │ ← Process exit (code 0)
└─────────────┘
```

### Error States

| State | Trigger | Exit Code | Log Level |
|-------|---------|-----------|-----------|
| CONFIG_ERROR | Malformed config file | 1 | ERROR |
| DB_ERROR | Database unreachable at startup | 1 | ERROR |
| PORT_IN_USE | Bind address/port unavailable | 1 | ERROR |
| STARTUP_FAILED | Any startup prerequisite fails | 1 | ERROR |

## Relationships

```
VPOConfig (existing)
    └── ServerConfig (new)
            │
            ▼
    DaemonLifecycle (runtime)
            │
            ├── ShutdownState
            │
            └── HealthStatus (generated on request)
```

## Validation Rules

### ServerConfig Validation

| Field | Rule | Error |
|-------|------|-------|
| `bind` | Valid IP address or hostname | "Invalid bind address" |
| `port` | 1-65535 inclusive | "Port must be 1-65535" |
| `port` | >1024 unless root | Warning: "Privileged port requires root" |
| `shutdown_timeout` | >0 | "Shutdown timeout must be positive" |

### Runtime Invariants

1. Only one shutdown can be initiated per daemon lifecycle
2. `ShutdownState.initiated` is immutable once set (monotonic)
3. Health endpoint always responds (even during shutdown)
4. Database check timeout is 5 seconds (to stay under 100ms p99 goal for healthy case)

## No Schema Changes

This feature does not modify the SQLite database schema. The daemon uses read-only queries:
- Health check: `SELECT 1` (connectivity verification)
- Future: May query job queue status for enhanced health checks

Database schema remains at version 7.
