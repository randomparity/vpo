# Systemd Integration

This guide covers deploying VPO as a systemd service on Linux systems.

## Quick Start

```bash
# 1. Copy the unit file
sudo cp docs/systemd/vpo.service /etc/systemd/system/

# 2. Create system user
sudo useradd --system --create-home --shell /bin/false vpo

# 3. Create configuration directory
sudo mkdir -p /etc/vpo
sudo cp ~/.vpo/config.toml /etc/vpo/ 2>/dev/null || true

# 4. Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable vpo

# 5. Start the service
sudo systemctl start vpo
```

## Service Management

```bash
# Start/stop/restart
sudo systemctl start vpo
sudo systemctl stop vpo
sudo systemctl restart vpo

# Check status
sudo systemctl status vpo

# View logs
journalctl -u vpo -f              # Follow logs
journalctl -u vpo --since today   # Today's logs
journalctl -u vpo -n 100          # Last 100 lines
```

## Configuration

The systemd unit expects a configuration file at `/etc/vpo/config.toml`:

```toml
[server]
bind = "127.0.0.1"
port = 8321
shutdown_timeout = 30

[logging]
level = "info"
format = "json"
```

### Environment Variables

Override settings via environment variables in the unit file:

```ini
[Service]
Environment=VPO_SERVER_PORT=9000
Environment=VPO_SERVER_BIND=0.0.0.0
```

Or use an environment file:

```ini
[Service]
EnvironmentFile=/etc/vpo/environment
```

## Health Checks

The daemon exposes a health endpoint:

```bash
curl http://127.0.0.1:8321/health
```

Response:
```json
{
  "status": "healthy",
  "database": "connected",
  "uptime_seconds": 3661.5,
  "version": "0.1.0",
  "shutting_down": false
}
```

## Security Hardening

The provided unit file includes several security options:

- `NoNewPrivileges=true`: Prevents privilege escalation
- `PrivateTmp=true`: Private /tmp directory
- `ProtectSystem=strict`: Read-only root filesystem
- `ProtectHome=read-only`: Read-only access to home directories

Customize `ReadWritePaths=` to allow access to your media directories.

## Troubleshooting

### Service won't start

```bash
# Check for configuration errors
journalctl -u vpo -n 50

# Test manually as the service user
sudo -u vpo /usr/local/bin/vpo serve --config /etc/vpo/config.toml
```

### Port already in use

```bash
# Find what's using the port
sudo lsof -i :8321

# Use a different port
sudo systemctl edit vpo
# Add:
# [Service]
# Environment=VPO_SERVER_PORT=9000
```

### Database permissions

```bash
# Ensure the vpo user owns the database directory
sudo chown -R vpo:vpo /home/vpo/.vpo
```

## Related Documentation

- [Daemon Mode](daemon-mode.md) - Full daemon configuration reference
- [Configuration](config.md) - Configuration file format
