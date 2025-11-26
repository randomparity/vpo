# Web UI Authentication

This guide covers how to protect your VPO web interface with HTTP Basic Authentication.

## Quick Start

Set the `VPO_AUTH_TOKEN` environment variable before starting the server:

```bash
export VPO_AUTH_TOKEN="your-secret-token"
vpo serve
```

When accessing the web UI, your browser will prompt for credentials:
- **Username**: Any value (ignored)
- **Password**: Your configured token

## Configuration Methods

### Environment Variable (Recommended)

The most secure method, especially for production deployments:

```bash
# Set the token
export VPO_AUTH_TOKEN="your-secret-token"

# Or inline with the command
VPO_AUTH_TOKEN="your-secret-token" vpo serve
```

### Configuration File

Add to `~/.vpo/config.toml`:

```toml
[server]
bind = "127.0.0.1"
port = 8321
auth_token = "your-secret-token"
```

### Precedence

Configuration is resolved in this order (highest priority first):

1. `VPO_AUTH_TOKEN` environment variable
2. `server.auth_token` in config file
3. No authentication (if neither is set)

## API Access

When authentication is enabled, API requests require Basic Auth:

```bash
# Using curl with credentials
curl -u "user:your-token" http://localhost:8321/api/jobs

# Or with explicit header
curl -H "Authorization: Basic $(echo -n 'user:your-token' | base64)" \
     http://localhost:8321/api/jobs
```

## Health Endpoint Exception

The `/health` endpoint is always accessible without authentication. This allows:
- Load balancer health checks
- Kubernetes liveness/readiness probes
- Monitoring system integration

```bash
# Always works, even with auth enabled
curl http://localhost:8321/health
```

## Disabling Authentication

To run without authentication (e.g., trusted localhost):

1. Unset the environment variable: `unset VPO_AUTH_TOKEN`
2. Remove or comment out `auth_token` in config file

A warning will be logged at startup when authentication is disabled.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 401 on all requests | Verify token matches exactly (case-sensitive) |
| Token not working | Check for trailing whitespace in env var or config |
| Browser not prompting | Clear browser cache or use incognito mode |
| Can't access health endpoint | `/health` should always work - check server is running |

## Security Considerations

**Important**: This authentication mechanism is minimal and designed for basic access control in trusted environments. It provides:

- Single shared token (no per-user accounts)
- HTTP Basic Authentication (credentials sent with each request)
- Constant-time token comparison (timing attack resistant)

**Limitations**:

- Credentials are base64-encoded, NOT encrypted
- No rate limiting for failed attempts
- No session management or token expiration
- No audit logging of access

**Recommendations for production**:

1. **Always use HTTPS** - Basic Auth credentials are visible without TLS
2. **Use a reverse proxy** - nginx, Caddy, or Traefik can add TLS and rate limiting
3. **Bind to localhost** - Default `127.0.0.1` binding is safest
4. **Strong tokens** - Use long, random tokens (e.g., `openssl rand -hex 32`)
5. **Network isolation** - Deploy on private networks when possible

## Related Documentation

- [Configuration](configuration.md) - General VPO configuration
- [CLI Usage](cli-usage.md) - Command-line interface reference
