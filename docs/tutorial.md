# Getting Started with VPO

This tutorial walks you through installing VPO, scanning your video library, and applying your first policy. By the end, you'll understand the core workflow and be ready to customize VPO for your needs.

## Prerequisites

Before starting, ensure you have:

- **Python 3.10 or higher** installed
- **ffmpeg** (includes ffprobe) installed on your system
- **A few video files** to work with (MKV or MP4 files with multiple audio/subtitle tracks work best)

### Installing ffmpeg

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Verify installation
ffprobe -version
```

## Step 1: Install VPO

Install VPO from PyPI:

```bash
pip install video-policy-orchestrator
```

Verify the installation:

```bash
vpo --version
vpo --help
```

Check that all external tools are available:

```bash
vpo doctor
```

You should see output indicating which tools are available. At minimum, you need `ffprobe` for scanning.

## Step 2: Scan Your Video Library

The `scan` command discovers video files and extracts their metadata into a local database.

### Scan a Directory

```bash
vpo scan /path/to/your/videos
```

For example, if your videos are in `~/Movies`:

```bash
vpo scan ~/Movies
```

### Understanding Scan Output

```
Scanning /home/user/Movies...
Found 42 video files
Introspecting files... [████████████████████████] 42/42
Scan complete: 42 files processed, 0 errors
```

VPO stores the scan results in a SQLite database at `~/.vpo/library.db`. Subsequent scans are incremental—only new or modified files are re-introspected.

### Scan Options

```bash
# Include subdirectories (default behavior)
vpo scan ~/Movies --recursive

# Scan multiple directories
vpo scan ~/Movies ~/TV

# Force re-scan of all files (ignore cache)
vpo scan ~/Movies --force
```

## Step 3: Inspect Individual Files

The `inspect` command shows detailed information about a specific video file.

```bash
vpo inspect /path/to/movie.mkv
```

### Example Output

```
File: movie.mkv
Container: matroska
Duration: 2:15:30
Size: 8.2 GB

Tracks:
  #0 video    h264      1920x1080  23.976fps
  #1 audio    aac       eng        stereo     "English 2.0"
  #2 audio    ac3       eng        5.1        "English 5.1" [default]
  #3 audio    aac       jpn        stereo     "Japanese"
  #4 subtitle subrip    eng        "English"  [default]
  #5 subtitle subrip    jpn        "Japanese"
```

This shows you:
- **Track index**: Position in the container
- **Track type**: video, audio, or subtitle
- **Codec**: The encoding format
- **Language**: ISO language code (eng, jpn, etc.)
- **Channels**: For audio (stereo, 5.1, etc.)
- **Title**: Track title metadata
- **Flags**: [default] and [forced] markers

## Step 4: Create a Policy

Policies are YAML files that describe how you want your video files organized. Create a file called `my-policy.yaml`:

```yaml
name: my-first-policy
version: "1.0"
description: Organize tracks with English preferred

rules:
  # Audio track ordering: English first, then others
  audio:
    order_by:
      - language: eng
      - language: "*"  # Everything else
    default: first     # First matching track becomes default

  # Subtitle ordering: English first
  subtitle:
    order_by:
      - language: eng
      - language: "*"
    default: first
```

### Policy Structure

- **name**: Unique identifier for your policy
- **version**: Policy version (for your tracking)
- **description**: Human-readable description
- **rules**: Track ordering and default flag rules

### Common Policy Patterns

**Prefer Japanese audio with English subtitles (anime):**

```yaml
rules:
  audio:
    order_by:
      - language: jpn
      - language: eng
    default: first

  subtitle:
    order_by:
      - language: eng
      - language: jpn
    default:
      language: eng
```

**Prefer highest quality audio (5.1 over stereo):**

```yaml
rules:
  audio:
    order_by:
      - channels: ">=6"  # 5.1 and above
      - channels: "*"
    default: first
```

## Step 5: Preview Changes (Dry Run)

Always preview what VPO will do before applying changes:

```bash
vpo apply --policy my-policy.yaml /path/to/movie.mkv --dry-run
```

### Example Dry-Run Output

```
Evaluating: movie.mkv

Planned changes:
  - Reorder audio tracks: [2, 1, 3] → [1, 2, 3] (English first)
  - Set default audio: track 1 (was track 2)
  - Set default subtitle: track 4 (unchanged)

No changes applied (dry-run mode)
```

The dry-run shows you exactly what VPO would change without modifying any files.

## Step 6: Apply the Policy

Once you're satisfied with the planned changes, apply the policy:

```bash
vpo apply --policy my-policy.yaml /path/to/movie.mkv
```

### Apply to Multiple Files

```bash
# Apply to all files in a directory
vpo apply --policy my-policy.yaml ~/Movies/

# Apply to specific files
vpo apply --policy my-policy.yaml movie1.mkv movie2.mkv
```

### Verify Changes

After applying, inspect the file again to confirm the changes:

```bash
vpo inspect /path/to/movie.mkv
```

## Next Steps

Now that you understand the basics, explore these topics:

- **[CLI Usage](usage/cli-usage.md)** - Complete command reference
- **[Configuration](usage/configuration.md)** - Customize VPO behavior
- **[Plugin Development](plugins.md)** - Extend VPO with custom plugins
- **[Transcode Policy](usage/transcode-policy.md)** - Convert video codecs

## Troubleshooting

### "Command not found: vpo"

Ensure Python's script directory is in your PATH:

```bash
# Check where pip installed vpo
pip show video-policy-orchestrator

# Add to PATH if needed (adjust for your system)
export PATH="$HOME/.local/bin:$PATH"
```

### "ffprobe not found"

Install ffmpeg which includes ffprobe:

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

### "No files found to scan"

Check that:
1. The path exists and contains video files
2. Files have recognized extensions (.mkv, .mp4, .avi, .webm, .m4v, .mov)
3. You have read permissions on the files

### Policy not applying changes

1. Run with `--dry-run` first to see planned changes
2. Check that the policy YAML syntax is valid
3. Verify the file matches the policy's track selectors

## Getting Help

- **Documentation**: [docs/INDEX.md](INDEX.md)
- **Issues**: [GitHub Issues](https://github.com/randomparity/vpo/issues)
- **Check tool status**: `vpo doctor`
