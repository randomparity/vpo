# Configuration

**Purpose:**
This document describes VPO's configuration options, including command-line flags, default paths, and how to customize behavior.

---

## Overview

VPO currently uses command-line flags for all configuration. Future versions may add support for configuration files and environment variables.

---

## Configuration Options

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

VPO relies on external tools that must be available in your PATH:

| Tool | Required For | Installation |
|------|--------------|--------------|
| `ffprobe` | `vpo inspect` command | Part of ffmpeg package |

### Checking Tool Availability

```bash
# Check ffprobe is available
which ffprobe
ffprobe -version
```

---

## Output Formats

Both `scan` and `inspect` commands support multiple output formats:

| Format | Flag | Use Case |
|--------|------|----------|
| Human | (default) | Interactive terminal use |
| JSON | `--json` or `--format json` | Scripting and automation |

---

## Planned Configuration

Future releases may include:

- **Configuration file:** `~/.vpo/config.yaml` for persistent settings
- **Environment variables:** `VPO_DB_PATH`, `VPO_EXTENSIONS`, etc.
- **Policy files:** YAML/JSON files defining library organization rules
- **Plugin directories:** Custom paths for loading extension plugins

---

## Related docs

- [Documentation Index](../INDEX.md)
- [CLI Usage](cli-usage.md)
- [Workflows](workflows.md)
- [Architecture Overview](../overview/architecture.md)
