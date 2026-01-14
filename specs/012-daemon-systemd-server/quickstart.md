# Quickstart: Daemon Mode Implementation

**Feature**: 012-daemon-systemd-server
**Date**: 2025-11-23

## Prerequisites

- Python 3.10+
- Existing VPO installation (`uv pip install -e ".[dev]"`)
- SQLite database initialized (`~/.vpo/library.db`)

## New Dependency

Add to `pyproject.toml`:
```toml
dependencies = [
    # ... existing deps ...
    "aiohttp>=3.9",
]
```

## Implementation Order

### Step 1: Configuration Extension

**File**: `src/vpo/config/models.py`

Add `ServerConfig` dataclass:
```python
@dataclass
class ServerConfig:
    bind: str = "127.0.0.1"
    port: int = 8321
    shutdown_timeout: float = 30.0
```

Add to `VPOConfig`:
```python
server: ServerConfig = field(default_factory=ServerConfig)
```

**File**: `src/vpo/config/loader.py`

Add environment variable loading for server settings.

### Step 2: Server Module

**Create**: `src/vpo/server/`

```
server/
├── __init__.py      # Exports DaemonServer
├── app.py           # aiohttp Application, /health route
├── lifecycle.py     # DaemonLifecycle, ShutdownState
└── signals.py       # Signal handler setup
```

**Key Classes**:
- `DaemonServer`: Main server class, orchestrates lifecycle
- `DaemonLifecycle`: Manages startup/shutdown state
- `HealthStatus`: Response model for /health

### Step 3: CLI Command

**File**: `src/vpo/cli/serve.py`

```python
@click.command("serve")
@click.option("--bind", type=str, help="Bind address")
@click.option("--port", type=int, help="Port number")
@click.option("--config", type=click.Path(exists=True), help="Config file path")
@click.pass_context
def serve(ctx, bind, port, config):
    """Run VPO as a background daemon."""
    # Load config, apply CLI overrides
    # Initialize logging for daemon mode
    # Start server, wait for shutdown
```

**Register in**: `src/vpo/cli/__init__.py`

### Step 4: Documentation

**Create**: `docs/daemon-mode.md`
**Create**: `docs/systemd/vpo.service`

### Step 5: Tests

**Create**: `tests/unit/server/test_lifecycle.py`
**Create**: `tests/unit/server/test_signals.py`
**Create**: `tests/integration/test_serve_command.py`

## Verification Commands

```bash
# Run daemon in foreground
uv run vpo serve

# Run with custom port
uv run vpo serve --port 9000

# Check health endpoint
curl http://127.0.0.1:8321/health

# Run with JSON logging
uv run vpo serve --log-json

# Test graceful shutdown
uv run vpo serve &
PID=$!
sleep 2
kill -TERM $PID
# Should see "Received SIGTERM, initiating shutdown" in logs
```

## Integration Test Pattern

```python
import subprocess
import time
import requests

def test_serve_command_starts_and_responds():
    proc = subprocess.Popen(
        ["uv", "run", "vpo", "serve", "--port", "19321"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        time.sleep(2)  # Wait for startup
        resp = requests.get("http://127.0.0.1:19321/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
    finally:
        proc.terminate()
        proc.wait(timeout=35)
```

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| "Address already in use" | Port 8321 occupied | Use `--port` to choose different port |
| "Database not found" | No prior scan | Run `vpo scan /path/to/media` first |
| "Permission denied" | Port <1024 | Use unprivileged port or run as root |
| Health returns 503 | DB file locked | Check for other VPO processes |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Clean shutdown |
| 1 | Startup failure (config, DB, port) |
| 130 | Interrupted (SIGINT) |
| 143 | Terminated (SIGTERM) |
