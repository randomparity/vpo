# Configuration

**Purpose:**
This document describes VPO's configuration options, including command-line flags, environment variables, configuration files, and how to customize behavior.

---

## Overview

VPO supports configuration through multiple mechanisms with the following precedence (highest to lowest):

1. **CLI arguments** - Highest priority
2. **Environment variables** - `VPO_*` prefixed variables
3. **Configuration file** - `~/.vpo/config.toml`
4. **Default values** - Built-in defaults

### Configuration Precedence

When the same setting is specified in multiple sources, the highest-precedence source wins. For example:

```bash
# config.toml says port = 8000
# Environment says VPO_SERVER_PORT=9000
# CLI says --port 7000

# Result: port = 7000 (CLI wins)
```

To see which source provided each value, run with `--log-level debug` and look for `Config <field> = <value> (from <source>)` messages.

---

## Configuration File

VPO uses a TOML configuration file located at `~/.vpo/config.toml`. Create this file with `vpo init` or manually.

### Example Configuration

```toml
# External tool paths (optional - defaults to system PATH)
[tools]
ffmpeg = "/opt/ffmpeg-7/bin/ffmpeg"
ffprobe = "/opt/ffmpeg-7/bin/ffprobe"
mkvmerge = "/usr/local/bin/mkvmerge"
mkvpropedit = "/usr/local/bin/mkvpropedit"

# Tool detection settings
[tools.detection]
cache_ttl_hours = 24              # How long to cache tool capabilities
auto_detect_on_startup = true     # Detect tools on first use

# Runtime behavior
[behavior]
warn_on_missing_features = true   # Warn when optional features unavailable
show_upgrade_suggestions = true   # Show upgrade hints for old versions

# Batch processing settings
[processing]
workers = 2                       # Number of parallel workers (1 = sequential)
```

### Configuration File Location

The config file location can be overridden:

```bash
export VPO_CONFIG_PATH=/path/to/custom/config.toml
```

### Validating Configuration

Use `vpo config check` to validate your config file:

```bash
# Check default config.toml
vpo config check

# Check a specific file
vpo config check --config /path/to/config.toml

# JSON output for scripting
vpo config check --json
```

### Unknown Key Detection

VPO warns about unrecognized keys in `config.toml` to help catch typos. For example, `[servr]` instead of `[server]` will produce a warning but parsing continues normally.

---

## Boolean Values

Environment variables that accept boolean values recognize the following (case-insensitive):

| True values | False values |
|-------------|--------------|
| `true`, `1`, `yes`, `on` | Any other non-empty value |

Empty string or unset variables return the default value.

---

## Environment Variables

### Paths and General

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VPO_CONFIG_PATH` | path | `~/.vpo/config.toml` | Config file location |
| `VPO_DATA_DIR` | path | `~/.vpo/` | VPO data directory |
| `VPO_DATABASE_PATH` | path | `~/.vpo/library.db` | Database file path |
| `VPO_TEMP_DIR` | path | (source dir) | Temp directory for intermediate files |
| `VPO_PLUGIN_DIRS` | paths | (empty) | Colon-separated plugin directories |

### Tool Paths

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VPO_FFMPEG_PATH` | path | (PATH lookup) | ffmpeg executable |
| `VPO_FFPROBE_PATH` | path | (PATH lookup) | ffprobe executable |
| `VPO_MKVMERGE_PATH` | path | (PATH lookup) | mkvmerge executable |
| `VPO_MKVPROPEDIT_PATH` | path | (PATH lookup) | mkvpropedit executable |

### Detection

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VPO_CACHE_TTL_HOURS` | int | `24` | Tool capability cache TTL (hours) |
| `VPO_AUTO_DETECT_ON_STARTUP` | bool | `true` | Auto-detect tools on startup |

### Behavior

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VPO_WARN_ON_MISSING_FEATURES` | bool | `true` | Warn when features unavailable |
| `VPO_SHOW_UPGRADE_SUGGESTIONS` | bool | `true` | Show tool upgrade suggestions |

### Plugins

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VPO_PLUGIN_AUTO_LOAD` | bool | `true` | Auto-load plugins on startup |
| `VPO_PLUGIN_WARN_UNACKNOWLEDGED` | bool | `true` | Warn about unacknowledged plugins |

### Plugin Metadata (Radarr/Sonarr)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VPO_RADARR_URL` | str | (none) | Radarr server URL |
| `VPO_RADARR_API_KEY` | str | (none) | Radarr API key |
| `VPO_RADARR_ENABLED` | bool | `true` | Enable Radarr plugin |
| `VPO_RADARR_TIMEOUT` | int | `30` | Radarr request timeout (seconds) |
| `VPO_SONARR_URL` | str | (none) | Sonarr server URL |
| `VPO_SONARR_API_KEY` | str | (none) | Sonarr API key |
| `VPO_SONARR_ENABLED` | bool | `true` | Enable Sonarr plugin |
| `VPO_SONARR_TIMEOUT` | int | `30` | Sonarr request timeout (seconds) |

### Jobs

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VPO_JOBS_RETENTION_DAYS` | int | `30` | Days to keep completed jobs |
| `VPO_JOBS_AUTO_PURGE` | bool | `true` | Purge old jobs on worker start |
| `VPO_JOBS_BACKUP_ORIGINAL` | bool | `true` | Keep backup after transcode |
| `VPO_LOG_COMPRESSION_DAYS` | int | `7` | Days before compressing job logs |
| `VPO_LOG_DELETION_DAYS` | int | `90` | Days before deleting job logs |
| `VPO_MIN_FREE_DISK_PERCENT` | float | `5.0` | Minimum free disk % (0 = disable) |
| `VPO_AUTO_PRUNE_ENABLED` | bool | `false` | Periodically prune missing files |
| `VPO_AUTO_PRUNE_INTERVAL_HOURS` | int | `168` | Hours between auto-prune runs |

### Worker

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VPO_WORKER_MAX_FILES` | int | (unlimited) | Max files per worker run |
| `VPO_WORKER_MAX_DURATION` | int | (unlimited) | Max seconds per worker run |
| `VPO_WORKER_END_BY` | str | (none) | End time HH:MM (24h) |
| `VPO_WORKER_CPU_CORES` | int | (auto) | CPU cores for transcoding |

### Processing

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VPO_PROCESSING_WORKERS` | int | `2` | Parallel workers for batch processing |

### Server

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VPO_SERVER_BIND` | str | `127.0.0.1` | Network address to bind to |
| `VPO_SERVER_PORT` | int | `8321` | HTTP port |
| `VPO_SERVER_SHUTDOWN_TIMEOUT` | float | `30.0` | Graceful shutdown timeout (seconds) |
| `VPO_AUTH_TOKEN` | str | (none) | Shared secret for HTTP Basic Auth (min 16 chars) |
| `VPO_SESSION_SECRET` | str | (random) | Fernet key for session encryption |

### Rate Limiting

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VPO_RATE_LIMIT_ENABLED` | bool | `true` | Enable API rate limiting |
| `VPO_RATE_LIMIT_GET_MAX_REQUESTS` | int | `120` | Max GET requests per window |
| `VPO_RATE_LIMIT_MUTATE_MAX_REQUESTS` | int | `30` | Max POST/PUT/DELETE per window |
| `VPO_RATE_LIMIT_WINDOW_SECONDS` | int | `60` | Sliding window duration |

### Language

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VPO_LANGUAGE_STANDARD` | str | `639-2/B` | ISO standard for language codes |
| `VPO_LANGUAGE_WARN_ON_CONVERSION` | bool | `true` | Warn on language code conversion |

### Transcription

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VPO_TRANSCRIPTION_PLUGIN` | str | (auto) | Transcription plugin to use |
| `VPO_TRANSCRIPTION_MODEL_SIZE` | str | `base` | Whisper model size |
| `VPO_TRANSCRIPTION_SAMPLE_DURATION` | int | `30` | Audio sample seconds (0 = full) |
| `VPO_TRANSCRIPTION_GPU_ENABLED` | bool | `true` | Use GPU if available |
| `VPO_TRANSCRIPTION_MAX_SAMPLES` | int | `3` | Max samples for language detection |
| `VPO_TRANSCRIPTION_CONFIDENCE_THRESHOLD` | float | `0.85` | Confidence to stop sampling |
| `VPO_TRANSCRIPTION_INCUMBENT_BONUS` | float | `0.15` | Vote bonus for existing tag |

### Feature Flags

Feature flags use `VPO_FEATURE_{FLAG}` environment variables. Set to `1` to enable.

No flags are currently defined. The infrastructure exists for future gradual rollouts.

---

## Plugin Configuration

### Metadata Plugins (Radarr/Sonarr)

Configure in `config.toml`:

```toml
[plugins.metadata.radarr]
url = "http://localhost:7878"
api_key = "<your-radarr-api-key>"
enabled = true
timeout_seconds = 30

[plugins.metadata.sonarr]
url = "http://localhost:8989"
api_key = "<your-sonarr-api-key>"
enabled = true
timeout_seconds = 30
```

Or via environment variables:

```bash
export VPO_RADARR_URL="http://localhost:7878"
export VPO_RADARR_API_KEY="<your-radarr-api-key>"
export VPO_SONARR_URL="http://localhost:8989"
export VPO_SONARR_API_KEY="<your-sonarr-api-key>"
```

---

## Security and Secrets

### API Keys

For production deployments, use environment variables instead of storing API keys in `config.toml`:

```bash
# Recommended: use environment variables
export VPO_RADARR_API_KEY="<your-radarr-key>"
export VPO_SONARR_API_KEY="<your-sonarr-key>"
export VPO_AUTH_TOKEN="<your-auth-token>"
```

### Session Secret

The `VPO_SESSION_SECRET` environment variable controls session encryption for the web UI. If not set, VPO generates a random key on each startup (sessions will not persist across restarts).

Generate a key:

```bash
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

### Auth Token

`VPO_AUTH_TOKEN` must be at least 16 characters. Whitespace-only values are treated as unset.

---

## CLI Configuration Options

### Database Path

**Default:** `~/.vpo/library.db`

The database stores all scanned file metadata and track information. Override with:

```bash
vpo scan --db /path/to/custom.db /media/videos
```

The parent directory is created automatically if it doesn't exist.

### File Extensions

**Default:** `mkv`, `mp4`, `avi`, `webm`, `m4v`, `mov`

Control which file types are scanned:

```bash
# Scan only MKV and MP4 files
vpo scan --extensions mkv,mp4 /media/videos

# Include additional formats
vpo scan --extensions mkv,mp4,avi,ts,m2ts /media/videos
```

Extensions are case-insensitive and can include or omit the leading dot.

---

## Default Paths

| Path | Purpose |
|------|---------|
| `~/.vpo/` | VPO data directory |
| `~/.vpo/library.db` | Default SQLite database |
| `~/.vpo/config.toml` | Configuration file |
| `~/.vpo/plugins/` | Plugin directory |
| `~/.vpo/profiles/` | Configuration profiles |
| `~/.vpo/logs/` | Log files |
| `~/.vpo/backups/` | Database backups |

---

## External Dependencies

VPO relies on external tools for media processing. See [External Tools Guide](external-tools.md) for detailed installation and configuration instructions.

| Tool | Required For | Installation |
|------|--------------|--------------|
| `ffprobe` | `vpo inspect` command | Part of ffmpeg package |
| `ffmpeg` | Non-MKV metadata editing | Part of ffmpeg package |
| `mkvmerge` | MKV track reordering | Part of mkvtoolnix package |
| `mkvpropedit` | MKV metadata editing | Part of mkvtoolnix package |

### Checking Tool Availability

Use the `vpo doctor` command to check all tools:

```bash
# Basic health check
vpo doctor

# Detailed output with versions and capabilities
vpo doctor --verbose

# Force refresh detection cache
vpo doctor --refresh
```

---

## Output Formats

Both `scan` and `inspect` commands support multiple output formats:

| Format | Flag | Use Case |
|--------|------|----------|
| Human | (default) | Interactive terminal use |
| JSON | `--json` or `--format json` | Scripting and automation |

---

## Capability Cache

VPO caches detected tool capabilities to avoid repeated subprocess calls:

| Setting | Default | Description |
|---------|---------|-------------|
| Cache location | `~/.vpo/tool-capabilities.json` | Stores detected capabilities |
| Cache TTL | 24 hours | How long cache remains valid |
| Auto-refresh | On path change | Re-detects if tool paths change |

To manually refresh the cache:

```bash
vpo doctor --refresh
```

---

## Related docs

- [Documentation Index](../INDEX.md)
- [External Tools Guide](external-tools.md)
- [CLI Usage](cli-usage.md)
- [Workflows](workflows.md)
- [Architecture Overview](../overview/architecture.md)
