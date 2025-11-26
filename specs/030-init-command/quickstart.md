# Quickstart: VPO Init Command

**Date**: 2025-11-25
**Feature**: 030-init-command

## Overview

The `vpo init` command initializes VPO's configuration directory with default settings and a starter policy file.

## Basic Usage

### Initialize VPO (First Time)

```bash
# Initialize with default location (~/.vpo/)
vpo init
```

**Output**:
```
Created /home/user/.vpo/
Created /home/user/.vpo/config.toml
Created /home/user/.vpo/policies/
Created /home/user/.vpo/policies/default.yaml
Created /home/user/.vpo/plugins/

VPO initialized successfully!

Next steps:
  1. Review configuration: ~/.vpo/config.toml
  2. Verify setup: vpo doctor
  3. Scan your library: vpo scan /path/to/videos
```

### Preview Changes (Dry Run)

```bash
# See what would be created without making changes
vpo init --dry-run
```

**Output**:
```
Would create /home/user/.vpo/
Would create /home/user/.vpo/config.toml
Would create /home/user/.vpo/policies/
Would create /home/user/.vpo/policies/default.yaml
Would create /home/user/.vpo/plugins/

No changes made (dry run).
```

### Custom Data Directory

```bash
# Initialize in a custom location
vpo init --data-dir /mnt/nas/vpo-config
```

### Re-initialize (Force Overwrite)

```bash
# Reset to defaults (overwrites existing config!)
vpo init --force
```

**Output**:
```
Warning: Overwriting existing configuration at /home/user/.vpo/

Replaced /home/user/.vpo/config.toml
Replaced /home/user/.vpo/policies/default.yaml

VPO re-initialized with defaults.
```

## Command Reference

```
vpo init [OPTIONS]

Options:
  --data-dir PATH  Use custom data directory instead of ~/.vpo/
  --force          Overwrite existing configuration files
  --dry-run        Show what would be created without making changes
  --help           Show this message and exit
```

## Generated Files

### config.toml

The configuration file contains all VPO settings with documentation:

```toml
# Video Policy Orchestrator Configuration
# Uncomment and modify settings as needed.

[tools]
# ffmpeg = "/path/to/ffmpeg"
# ffprobe = "/path/to/ffprobe"

[server]
# bind = "127.0.0.1"
# port = 8321

[logging]
# level = "info"
# format = "text"
```

### policies/default.yaml

A starter policy demonstrating common track ordering:

```yaml
schema_version: 1

track_order:
  - video
  - audio_main
  - subtitle_main

audio_language_preference:
  - eng
```

## Common Scenarios

### Already Initialized

```bash
$ vpo init
Error: VPO is already initialized at /home/user/.vpo/

Existing files:
  - config.toml
  - policies/default.yaml

Use --force to overwrite existing configuration.
```

### Permission Denied

```bash
$ vpo init --data-dir /root/vpo
Error: Cannot write to /root/vpo/: Permission denied

Try running with appropriate permissions or choose a different location.
```

### Path Conflict

```bash
$ vpo init --data-dir /home/user/.vpo-config
Error: Cannot create directory at /home/user/.vpo-config: A file already exists at this location.
```

## Integration with Other Commands

After initialization, typical workflow:

```bash
# 1. Initialize VPO
vpo init

# 2. Verify setup (checks for required tools)
vpo doctor

# 3. Scan your video library
vpo scan /path/to/videos

# 4. Apply the default policy (preview first)
vpo apply --policy ~/.vpo/policies/default.yaml --dry-run /path/to/video.mkv

# 5. Start the web UI
vpo serve
```

## Environment Variables

The init command respects VPO_DATA_DIR:

```bash
# Set custom data directory via environment
export VPO_DATA_DIR=/mnt/nas/vpo
vpo init  # Creates files in /mnt/nas/vpo/
```

Note: `--data-dir` flag takes precedence over VPO_DATA_DIR.
