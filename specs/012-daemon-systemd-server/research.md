# Research: Daemon Mode & Systemd-Friendly Server

**Feature**: 012-daemon-systemd-server
**Date**: 2025-11-23
**Status**: Complete

## Research Tasks

### 1. HTTP Framework Selection for Health Endpoint

**Decision**: aiohttp

**Rationale**:
- Lightweight async HTTP server with minimal dependencies
- Native asyncio integration matches Python's signal handling patterns
- No heavy framework overhead (unlike FastAPI/Django)
- Well-suited for single-endpoint use case (health check)
- Production-ready with proper shutdown handling
- Already widely used in daemon/service contexts

**Alternatives Considered**:

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| aiohttp | Lightweight, async-native, mature | Learning curve for team | **Selected** |
| http.server | stdlib, no deps | Blocking, no graceful shutdown | Rejected |
| FastAPI | Modern, OpenAPI built-in | Heavy for single endpoint, pulls uvicorn | Rejected |
| Flask | Simple, familiar | WSGI blocking model, needs gunicorn | Rejected |
| Starlette | Light ASGI | Still needs uvicorn server | Rejected |

### 2. Signal Handling Best Practices for Python Daemons

**Decision**: Use asyncio signal handlers with graceful shutdown coordination

**Rationale**:
- `asyncio.get_event_loop().add_signal_handler()` integrates cleanly with async code
- Can coordinate shutdown across HTTP server and background tasks
- Handles both SIGTERM (systemd) and SIGINT (interactive) uniformly
- Allows setting a shutdown timeout with cancellation of remaining tasks

**Implementation Pattern**:
```python
import asyncio
import signal

class DaemonLifecycle:
    def __init__(self, shutdown_timeout: float = 30.0):
        self.shutdown_event = asyncio.Event()
        self.shutdown_timeout = shutdown_timeout

    def setup_signals(self, loop: asyncio.AbstractEventLoop):
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_signal, sig)

    def _handle_signal(self, sig: signal.Signals):
        logger.info(f"Received {sig.name}, initiating shutdown")
        self.shutdown_event.set()

    async def wait_for_shutdown(self):
        await self.shutdown_event.wait()
```

**Key Considerations**:
- Signal handlers must be registered on the main thread
- Use `asyncio.Event` for cross-task shutdown coordination
- Implement timeout-based task cancellation per FR-009

### 3. Configuration Extension Pattern

**Decision**: Extend existing `config/models.py` with `ServerConfig` dataclass

**Rationale**:
- Follows existing VPO pattern (all config in one place)
- Reuses existing TOML loading and precedence logic
- Consistent with existing `LoggingConfig`, `JobsConfig` patterns

**Config Schema**:
```toml
[server]
bind = "127.0.0.1"      # Default localhost for security
port = 8321             # Per clarification decision
shutdown_timeout = 30   # Seconds to wait for graceful shutdown
```

**Environment Variables** (following existing pattern):
- `VPO_SERVER_BIND`
- `VPO_SERVER_PORT`
- `VPO_SERVER_SHUTDOWN_TIMEOUT`

### 4. Health Check Implementation

**Decision**: Simple JSON response with database connectivity check

**Rationale**:
- Matches FR-027 through FR-030 requirements
- Fast (<100ms) by using simple SELECT 1 query
- No side effects (read-only check)
- Returns structured response for monitoring tools

**Response Schema**:
```json
{
  "status": "healthy",
  "database": "connected",
  "uptime_seconds": 12345,
  "version": "0.1.0"
}
```

**Status Codes**:
- 200 OK: All checks pass
- 503 Service Unavailable: Database unreachable or shutdown in progress

### 5. Logging in Daemon Mode

**Decision**: Reuse existing `logging/` module with daemon-specific defaults

**Rationale**:
- Existing module already supports JSON format (FR-016)
- Already outputs to stderr by default (FR-018, journald compatible)
- Minimal changes needed; just ensure no print() calls in daemon code path

**Daemon-Specific Behavior**:
- Default to INFO level (not WARNING as in CLI)
- Include `daemon=True` context in structured logs
- Suppress all interactive output (spinners, progress bars)

### 6. Systemd Integration Patterns

**Decision**: Type=simple service with example unit file

**Rationale**:
- `Type=simple` is correct for foreground daemons (process stays in foreground)
- systemd handles SIGTERM delivery and timeout enforcement
- Standard journald integration via stderr logging

**Unit File Template**:
```ini
[Unit]
Description=Video Policy Orchestrator Daemon
After=network.target

[Service]
Type=simple
User=vpo
Group=vpo
ExecStart=/usr/local/bin/vpo serve --config /etc/vpo/config.toml
Restart=on-failure
RestartSec=5
TimeoutStopSec=35

# Security hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### 7. Async Database Connection for Health Check

**Decision**: Use existing synchronous connection in thread pool executor

**Rationale**:
- SQLite is synchronous; no async driver available
- Health check is fast (SELECT 1), blocking briefly is acceptable
- `asyncio.to_thread()` (Python 3.9+) provides clean async wrapper
- Avoids adding aiosqlite dependency for single use case

**Pattern**:
```python
async def check_database_health(db_path: Path) -> bool:
    try:
        return await asyncio.to_thread(_sync_db_check, db_path)
    except Exception:
        return False

def _sync_db_check(db_path: Path) -> bool:
    with get_connection(db_path) as conn:
        conn.execute("SELECT 1")
        return True
```

## Summary

All technical decisions align with existing VPO patterns:
- Configuration via TOML file and environment variables
- Structured logging with JSON format support
- Click CLI command structure
- SQLite database access patterns

No external clarifications needed. Ready for Phase 1 design.
