# External Tools Guide

## Purpose

This guide explains how to install, configure, and troubleshoot the external tools that VPO depends on for media processing. It covers tool requirements, installation instructions, configuration options, and common issues.

## Required Tools

VPO uses the following external tools for media file operations:

| Tool | Package | Purpose |
|------|---------|---------|
| `ffprobe` | ffmpeg | Media file inspection (required) |
| `ffmpeg` | ffmpeg | Metadata modification for non-MKV files |
| `mkvmerge` | mkvtoolnix | Track reordering in MKV files |
| `mkvpropedit` | mkvtoolnix | Fast metadata editing in MKV files |

### Minimum Requirements

- **ffprobe**: Any recent version (required for `vpo inspect`)
- **ffmpeg**: Version 5.0+ recommended
- **mkvtoolnix**: Version 70.0+ recommended (mkvmerge and mkvpropedit)

## Installation

### Linux (Debian/Ubuntu)

```bash
# Install ffmpeg (includes ffprobe)
sudo apt update
sudo apt install ffmpeg

# Install mkvtoolnix
sudo apt install mkvtoolnix
```

### Linux (Fedora/RHEL)

```bash
# Install ffmpeg
sudo dnf install ffmpeg ffmpeg-devel

# Install mkvtoolnix
sudo dnf install mkvtoolnix
```

### macOS

```bash
# Using Homebrew
brew install ffmpeg mkvtoolnix
```

### Windows

1. **FFmpeg**: Download from [ffmpeg.org/download.html](https://ffmpeg.org/download.html)
   - Extract to a folder (e.g., `C:\ffmpeg`)
   - Add to PATH or configure in VPO settings

2. **MKVToolNix**: Download from [mkvtoolnix.download](https://mkvtoolnix.download/)
   - Run the installer
   - Tools are typically added to PATH automatically

## Verifying Installation

Use the `vpo doctor` command to check tool availability:

```bash
# Basic check
vpo doctor

# Detailed output with capabilities
vpo doctor --verbose

# Force refresh detection (ignore cache)
vpo doctor --refresh

# Output as JSON (for scripting)
vpo doctor --json
```

### Example Output

```text
VPO External Tool Health Check
========================================

FFmpeg Tools:
--------------------
  ✓ ffprobe: 6.1.1 (/usr/bin/ffprobe)
  ✓ ffmpeg:  6.1.1 (/usr/bin/ffmpeg)

MKVToolNix:
--------------------
  ✓ mkvmerge:    81.0 (/usr/bin/mkvmerge)
  ✓ mkvpropedit: 81.0 (/usr/bin/mkvpropedit)

Summary:
--------------------
  Available: 4/4 (ffmpeg, ffprobe, mkvmerge, mkvpropedit)

✓ All tools available and ready.
```

## Configuration

### Custom Tool Paths

If tools are not in your system PATH, you can configure custom paths.

#### Environment Variables

```bash
# Set custom paths via environment
export VPO_FFMPEG_PATH=/opt/ffmpeg-7/bin/ffmpeg
export VPO_FFPROBE_PATH=/opt/ffmpeg-7/bin/ffprobe
export VPO_MKVMERGE_PATH=/usr/local/bin/mkvmerge
export VPO_MKVPROPEDIT_PATH=/usr/local/bin/mkvpropedit
```

#### Configuration File

Create `~/.vpo/config.toml`:

```toml
[tools]
ffmpeg = "/opt/ffmpeg-7/bin/ffmpeg"
ffprobe = "/opt/ffmpeg-7/bin/ffprobe"
mkvmerge = "/usr/local/bin/mkvmerge"
mkvpropedit = "/usr/local/bin/mkvpropedit"

[tools.detection]
cache_ttl_hours = 24
auto_detect_on_startup = true

[behavior]
warn_on_missing_features = true
show_upgrade_suggestions = true
```

### Configuration Precedence

Configuration is loaded with the following precedence (highest to lowest):

1. CLI arguments
2. Environment variables (`VPO_*`)
3. Config file (`~/.vpo/config.toml`)
4. System PATH

## Capability Detection

VPO detects tool capabilities at runtime, including:

- **Version numbers**: For compatibility checking
- **FFmpeg build options**: GPL/LGPL, enabled features
- **Codec support**: Available encoders/decoders
- **Format support**: Supported container formats

### Detection Cache

To avoid repeated subprocess calls, detection results are cached:

- **Location**: `~/.vpo/tool-capabilities.json`
- **Default TTL**: 24 hours
- **Manual refresh**: `vpo doctor --refresh`

### FFmpeg Build Options

The verbose doctor output shows FFmpeg capabilities:

```bash
vpo doctor --verbose
```

```text
  ✓ ffmpeg:  6.1.1 (/usr/bin/ffmpeg)
    ├─ GPL build: yes
    ├─ Encoders: 200+
    ├─ Decoders: 400+
    ├─ Muxers: 150+
    └─ Filters: 450+
```

## Troubleshooting

### Tool Not Found

```text
Error: ffprobe is not installed or not in PATH
```

**Solutions**:
1. Install the missing tool (see Installation section)
2. Verify it's in PATH: `which ffprobe`
3. Configure custom path via environment variable or config file

### Version Too Old

```text
mkvtoolnix 70.0+ recommended for best compatibility. You have 65.0.
```

**Solutions**:
1. Update to a newer version
2. Use the official repositories (may have newer versions)
3. Build from source if needed

### Permission Denied

```text
Error: Permission denied: /usr/bin/ffmpeg
```

**Solutions**:
1. Check file permissions: `ls -la /usr/bin/ffmpeg`
2. Ensure the tool is executable: `chmod +x /usr/bin/ffmpeg`
3. Try running with appropriate privileges

### Timeout During Detection

If tool detection times out (default 10 seconds):

1. Check if the tool is responsive: `ffmpeg -version`
2. Look for system resource issues
3. Try detection with `vpo doctor --refresh`

## Feature Requirements

Different VPO features require different tools:

| Feature | Required Tools |
|---------|----------------|
| `vpo inspect` | ffprobe |
| `vpo process` (MKV metadata) | mkvpropedit |
| `vpo process` (MKV reorder) | mkvmerge |
| `vpo process` (MP4/AVI metadata) | ffmpeg |

If a required tool is missing, VPO will report an error with installation instructions.

## Related Docs

- [Configuration Guide](configuration.md) - Full configuration reference
- [CLI Usage](cli-usage.md) - Command reference
- [Architecture Overview](../overview/architecture.md) - System design
- [docs/INDEX.md](../INDEX.md) - Documentation index
