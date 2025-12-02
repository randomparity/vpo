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

---

## Configuration File

VPO uses a TOML configuration file located at `~/.vpo/config.toml`. Create this file to set persistent configuration options.

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

---

## Environment Variables

All configuration options can be set via environment variables:

### Tool Paths

```bash
export VPO_FFMPEG_PATH=/opt/ffmpeg-7/bin/ffmpeg
export VPO_FFPROBE_PATH=/opt/ffmpeg-7/bin/ffprobe
export VPO_MKVMERGE_PATH=/usr/local/bin/mkvmerge
export VPO_MKVPROPEDIT_PATH=/usr/local/bin/mkvpropedit
```

### Database and Paths

```bash
export VPO_DATABASE_PATH=/custom/path/library.db
export VPO_CONFIG_PATH=/custom/path/config.toml
```

### Detection Settings

```bash
export VPO_CACHE_TTL_HOURS=48
export VPO_AUTO_DETECT_ON_STARTUP=true
```

### Behavior Settings

```bash
export VPO_WARN_ON_MISSING_FEATURES=true
export VPO_SHOW_UPGRADE_SUGGESTIONS=true
```

### Processing Settings

```bash
export VPO_PROCESSING_WORKERS=4    # Default number of parallel workers
```

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

## Planned Configuration

Future releases may include:

- **Policy files:** YAML/JSON files defining library organization rules
- **Plugin directories:** Custom paths for loading extension plugins

---

## Related docs

- [Documentation Index](../INDEX.md)
- [External Tools Guide](external-tools.md)
- [CLI Usage](cli-usage.md)
- [Workflows](workflows.md)
- [Architecture Overview](../overview/architecture.md)
