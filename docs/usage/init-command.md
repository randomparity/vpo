# Init Command

**Purpose:**
This document describes the `vpo init` command, which initializes the VPO configuration directory with default settings and a starter policy.

---

## Overview

The `vpo init` command creates all necessary configuration files and directories for VPO. Running this command is the recommended first step after installing VPO.

```bash
vpo init [OPTIONS]
```

### What Gets Created

| Path | Description |
|------|-------------|
| `~/.vpo/` | VPO data directory |
| `~/.vpo/config.toml` | Configuration file with all settings documented |
| `~/.vpo/policies/` | Directory for policy files |
| `~/.vpo/policies/default.yaml` | Starter policy demonstrating common patterns |
| `~/.vpo/plugins/` | Directory for user plugins |

---

## Options

| Option | Description |
|--------|-------------|
| `--data-dir PATH` | Use a custom data directory instead of `~/.vpo/` |
| `--force` | Overwrite existing configuration files |
| `--dry-run` | Show what would be created without making changes |
| `--help` | Show help message and exit |

---

## Basic Usage

### First-Time Setup

```bash
# Initialize VPO with defaults
vpo init
```

**Output:**
```text
Created /home/user/.vpo/
Created /home/user/.vpo/policies/
Created /home/user/.vpo/plugins/
Created /home/user/.vpo/config.toml
Created /home/user/.vpo/policies/default.yaml

VPO initialized successfully!

Next steps:
  1. Review configuration: ~/.vpo/config.toml
  2. Verify setup: vpo doctor
  3. Scan your library: vpo scan /path/to/videos
```

### Preview Changes

Use `--dry-run` to see what would be created without making any changes:

```bash
vpo init --dry-run
```

**Output:**
```text
Would create /home/user/.vpo/
Would create /home/user/.vpo/policies/
Would create /home/user/.vpo/plugins/
Would create /home/user/.vpo/config.toml
Would create /home/user/.vpo/policies/default.yaml

No changes made (dry run).
```

### Custom Data Directory

Use `--data-dir` to initialize in a custom location:

```bash
vpo init --data-dir /mnt/nas/vpo
```

This is useful for:
- Storing configuration on a network share
- Using a different location for testing
- Separating VPO instances for different libraries

### Re-initialize with Defaults

If you want to reset your configuration to defaults, use `--force`:

```bash
vpo init --force
```

**Warning:** This overwrites existing files. Your custom configuration will be lost.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `VPO_DATA_DIR` | Default data directory (overridden by `--data-dir`) |

**Precedence:**
1. `--data-dir` CLI option (highest)
2. `VPO_DATA_DIR` environment variable
3. Default `~/.vpo/` (lowest)

**Example:**
```bash
# Set custom data directory via environment
export VPO_DATA_DIR=/mnt/nas/vpo
vpo init  # Creates files in /mnt/nas/vpo/
```

---

## Generated Files

### config.toml

The configuration file contains all VPO settings, organized by section. All settings are commented out with their default values shown:

```toml
# Video Policy Orchestrator Configuration
# Uncomment and modify settings as needed.

[tools]
# ffmpeg = "/path/to/ffmpeg"
# ffprobe = "/path/to/ffprobe"
# mkvmerge = "/path/to/mkvmerge"
# mkvpropedit = "/path/to/mkvpropedit"

[server]
# bind = "127.0.0.1"
# port = 8321

[logging]
# level = "info"
# format = "text"
```

See [Configuration](configuration.md) for detailed documentation of all settings.

### policies/default.yaml

The default policy demonstrates common track ordering patterns using V12 phased format:

```yaml
schema_version: 12

config:
  on_error: skip

phases:
  - name: organize
    track_order:
      - video
      - audio_main
      - subtitle_main

    audio_filter:
      languages: [eng]

    default_flags:
      set_first_video_default: true
      set_preferred_audio_default: true
```

This policy can be used as-is or customized for your library.

---

## Error Handling

### Already Initialized

If VPO is already initialized, the command shows existing files and exits:

```bash
$ vpo init
Error: VPO is already initialized at /home/user/.vpo/

Existing files:
  - config.toml
  - policies/default.yaml

Use --force to overwrite existing configuration.
```

### Permission Denied

If the target directory is not writable:

```bash
$ vpo init --data-dir /root/vpo
Error: Permission denied: cannot write to /root

Try running with appropriate permissions or choose a different location.
```

### Path Conflict

If the target path is an existing file:

```bash
$ vpo init --data-dir /home/user/.vpo-config
Error: A file already exists at this location: /home/user/.vpo-config
```

---

## Exit Codes

| Code | Description |
|------|-------------|
| `0` | Success |
| `1` | Error (already initialized, permission denied, etc.) |

---

## Workflow Integration

After initialization, the typical workflow is:

```bash
# 1. Initialize VPO
vpo init

# 2. Verify external tools are available
vpo doctor

# 3. Scan your video library
vpo scan /path/to/videos

# 4. Preview policy application
vpo policy run --policy ~/.vpo/policies/default.yaml --dry-run /path/to/video.mkv

# 5. Start the web UI (optional)
vpo serve
```

---

## Related docs

- [Configuration](configuration.md) - Detailed configuration options
- [CLI Usage](cli-usage.md) - Other CLI commands
- [Workflows](workflows.md) - End-to-end usage workflows
- [Tutorial](../tutorial.md) - Getting started guide
- [External Tools](external-tools.md) - Setting up ffmpeg and mkvtoolnix
