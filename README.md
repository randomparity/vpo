# Video Policy Orchestrator

A spec-driven tool for scanning, organizing, and transforming video libraries using user-defined policies and an extensible plugin architecture.

## Quickstart

### Prerequisites

VPO requires `ffprobe` (part of ffmpeg) for media introspection:

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows - download from https://ffmpeg.org/download.html
```

### Installation

```bash
# Install from source (development)
git clone https://github.com/randomparity/vpo.git
cd vpo
uv pip install -e ".[dev]"
uv run maturin develop  # Build Rust extension
```

### Basic Usage

```bash
# Scan a video library
vpo scan /path/to/videos

# Inspect a single file
vpo inspect /path/to/movie.mkv

# Apply a policy (preview changes first)
vpo apply --policy policy.yaml /path/to/movie.mkv --dry-run

# Check external tool availability
vpo doctor
```

📖 **See [docs/INDEX.md](docs/INDEX.md) for the complete user guide**

---

## Overview

Video Policy Orchestrator (VPO) analyzes video files and applies user-defined **policies** to:

- Normalize and reorder tracks (video, audio, subtitles)
- Standardize audio track ordering and metadata
- Apply metadata-only changes (default flags, language codes, titles)
- **Transcode** videos to target codecs (HEVC, H.264, VP9, AV1) with quality settings
- **Organize** files automatically based on metadata parsed from filenames
- Extend behavior via a **plugin system**

VPO acts as a **policy layer** on top of existing media tools (ffmpeg, mkvmerge):
- You define *what you want* your library to look like
- The tool figures out *how to get there* and keeps it that way over time

---

## Features

### Library Scanning & Database

- Recursively scan directories for video containers (mkv, mp4, avi, webm, m4v, mov)
- Extract container and track metadata via ffprobe
- Store results in SQLite database for incremental rescans
- Parallel file discovery via Rust extension for large libraries

### Policy-Driven Track Organization

- Define policies in YAML to specify track order and preferences
- Run in **dry-run** mode to preview changes before modifying files
- Apply metadata-only changes via mkvpropedit/ffmpeg

### Transcoding & Job Queue

- Transcode videos to HEVC, H.264, VP9, or AV1 with CRF or bitrate control
- Scale down videos exceeding a target resolution (1080p, 720p, etc.)
- Preserve lossless audio codecs (TrueHD, DTS-HD, FLAC) while transcoding others
- Queue-based processing with `vpo jobs start` for long-running operations
- Configurable limits for scheduled/cron integration (max files, duration, end time)

### Directory Organization

- Parse metadata from filenames (title, year, series, season, episode)
- Template-based file organization: `Movies/{year}/{title}`
- Automatic directory creation and file movement

### Plugin Architecture

- Extend VPO with custom analyzers, mutators, and transcribers
- Plugin discovery via Python entry points or plugin directories
- Plugin SDK with helpers for plugin authors
- Version compatibility checking and acknowledgment system

### CLI Commands

| Command | Description |
|---------|-------------|
| `vpo scan` | Scan directories for video files |
| `vpo inspect` | Display detailed track information |
| `vpo apply` | Apply a policy to media files |
| `vpo transcode` | Queue files for transcoding |
| `vpo jobs` | Manage job queue (list, start, cancel, cleanup) |
| `vpo doctor` | Check external tool availability |
| `vpo plugins` | Manage VPO plugins |

---

## Tech Stack

- **Python 3.10+** with click (CLI), pydantic (validation), PyYAML (config)
- **Rust** (PyO3/maturin) for parallel file discovery and hashing
- **SQLite** database at `~/.vpo/library.db`
- **External tools:** ffprobe (introspection), mkvpropedit/mkvmerge (MKV editing), ffmpeg (metadata)

---

## Documentation

- [Project Overview](docs/overview/project-overview.md) - Goals, use cases, and target users
- [Architecture](docs/overview/architecture.md) - System design and component interactions
- [CLI Usage](docs/usage/cli-usage.md) - Command reference and examples
- [Configuration](docs/usage/configuration.md) - Config files and options
- [Transcode Policy](docs/usage/transcode-policy.md) - Video transcoding settings
- [Job Queue](docs/usage/jobs.md) - Managing long-running operations
- [Plugin Development](docs/plugins.md) - Creating custom plugins

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
- Spec-driven development workflow
- Code style and testing requirements
- Pull request process

---

## License

[MIT License](LICENSE) - Copyright (c) 2025 David Christensen
