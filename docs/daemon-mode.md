# Daemon Mode

VPO can run as a long-lived background service using the `vpo serve` command. This is useful for:

- Running VPO as a systemd service
- Continuous health monitoring via HTTP endpoint
- Integration with container orchestration

## Quick Start

```bash
# Start daemon on default port (8321)
vpo serve

# Start with custom port
vpo serve --port 9000

# Start with JSON logging for production
vpo serve --log-format json
```

## Configuration

### CLI Options

```text
vpo serve [OPTIONS]

Options:
  -c, --config PATH        Path to configuration file
  --bind TEXT              Address to bind to (default: 127.0.0.1)
  -p, --port INTEGER       Port to bind to (default: 8321)
  --log-level [debug|info|warning|error]
                           Override log level (default: info)
  --log-format [text|json] Log format (default: text)
```

### Configuration File

Add a `[server]` section to `~/.vpo/config.toml`:

```toml
[server]
bind = "127.0.0.1"      # Network bind address
port = 8321             # HTTP server port
shutdown_timeout = 30   # Graceful shutdown timeout in seconds
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VPO_SERVER_BIND` | `127.0.0.1` | Network bind address |
| `VPO_SERVER_PORT` | `8321` | HTTP server port |
| `VPO_SERVER_SHUTDOWN_TIMEOUT` | `30` | Shutdown timeout (seconds) |

### Configuration Precedence

1. CLI flags (highest priority)
2. Configuration file (`--config` or `~/.vpo/config.toml`)
3. Environment variables
4. Default values (lowest priority)

## Web UI

The daemon includes a web-based user interface for monitoring and management. Access it at:

```text
http://127.0.0.1:8321/
```

### Navigation Sections

The UI provides five main sections accessible via the sidebar:

| Section | Path | Description |
|---------|------|-------------|
| Jobs | `/jobs` | View and manage processing jobs |
| Library | `/library` | Browse media library |
| Transcriptions | `/transcriptions` | View transcription results |
| Policies | `/policies` | Manage policies |
| Approvals | `/approvals` | Review pending approvals |

### Responsive Design

The Web UI supports:
- **Desktop** (1024px+): Full sidebar navigation
- **Tablet** (768-1023px): Compact sidebar
- **Below 768px**: Horizontal navigation (graceful degradation)

### Security Headers

All HTML responses include security headers:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`

Static files include `Cache-Control: public, max-age=3600` for caching.

## Health Endpoint

The daemon exposes a health check at `/health`:

```bash
curl http://127.0.0.1:8321/health
```

### Response Format

```json
{
  "status": "healthy",
  "database": "connected",
  "uptime_seconds": 3661.5,
  "version": "0.2.0",
  "shutting_down": false
}
```

### Status Codes

| HTTP Code | Status | Condition |
|-----------|--------|-----------|
| 200 | `healthy` | Database connected, not shutting down |
| 503 | `degraded` | Database disconnected |
| 503 | `unhealthy` | Graceful shutdown in progress |

## Signal Handling

The daemon handles the following signals:

- **SIGTERM**: Initiates graceful shutdown (used by systemd)
- **SIGINT**: Initiates graceful shutdown (Ctrl+C)

During graceful shutdown:
1. Health endpoint returns 503 with `shutting_down: true`
2. In-flight requests are allowed to complete
3. After timeout, remaining tasks are cancelled
4. Clean exit with code 0

## Logging

### Text Format (Default)

```text
2024-01-15 10:30:00 INFO VPO daemon started on http://127.0.0.1:8321 (PID 12345)
```

### JSON Format

Use `--log-format json` for structured logging:

```bash
vpo serve --log-format json
```

Output:
```json
{"timestamp":"2024-01-15T10:30:00.000Z","level":"INFO","message":"VPO daemon started on http://127.0.0.1:8321 (PID 12345)","logger":"vpo.cli.serve"}
```

JSON format is recommended for:
- systemd/journald integration
- Log aggregation systems (ELK, Splunk, etc.)
- Container deployments

## Systemd Integration

See [systemd.md](systemd.md) for deployment as a systemd service.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Clean shutdown |
| 1 | Startup failure (config, database, port) |
| 130 | Interrupted (SIGINT) |
| 143 | Terminated (SIGTERM) |

## Security Considerations

- **Default bind address**: `127.0.0.1` (localhost only) for security
- **No authentication**: The health endpoint has no authentication; expose only on trusted networks
- **Privileged ports**: Ports below 1024 require root privileges

To expose on all interfaces:
```bash
vpo serve --bind 0.0.0.0
```

## Related docs

- [Systemd Integration](systemd.md) - Deploy as a system service
- [Configuration](usage/configuration.md) - Full configuration reference
