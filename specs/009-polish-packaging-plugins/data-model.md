# Data Model: Polish, Packaging, and Plugin Ecosystem Readiness

**Feature Branch**: `009-polish-packaging-plugins`
**Date**: 2025-11-22

## Overview

This feature introduces **no new data models**. All work involves:
- CI/CD configuration (YAML workflows)
- Documentation (Markdown files)
- Container configuration (Dockerfile)
- Project management artifacts (GitHub Issues, labels)

## Existing Models Referenced

The following existing models are documented in this feature but not modified:

### Plugin Manifest (from plugin system)

```python
# Documented in docs/plugins.md and plugin-author-guide.md
@dataclass
class PluginManifest:
    name: str           # Unique identifier (kebab-case)
    version: str        # Plugin version (semver)
    description: str    # Human-readable description
    author: str         # Plugin author
    events: list[str]   # Events to subscribe to
    min_api_version: str = "1.0.0"
    max_api_version: str = "1.99.99"
```

### FileInfo (from database)

```python
# Referenced in tutorial.md for scan/inspect output
@dataclass
class FileInfo:
    id: str             # UUID
    path: Path          # File path
    filename: str       # Filename only
    container: str      # Container format (mkv, mp4, etc.)
    size_bytes: int     # File size
    duration_seconds: float
    created_at: datetime
    last_scanned_at: datetime
```

### TrackInfo (from database)

```python
# Referenced in tutorial.md for inspect output
@dataclass
class TrackInfo:
    id: str             # UUID
    file_id: str        # FK to FileInfo
    index: int          # Track index in container
    track_type: str     # video, audio, subtitle
    codec: str          # Codec name
    language: str       # ISO 639 language code
    title: str          # Track title
    default: bool       # Default flag
    forced: bool        # Forced flag
```

## Configuration Artifacts

### CI Workflow Schema (release.yml)

```yaml
# Not a data model, but defines structure for release automation
trigger:
  tags: ["v*"]

platforms:
  - os: ubuntu-latest
    arch: x86_64
  - os: macos-13
    arch: x86_64
  - os: macos-14
    arch: arm64

python_versions: ["3.10", "3.11", "3.12"]

outputs:
  - wheels/*.whl
  - sdist/*.tar.gz
```

### Container Image Schema

```yaml
# Defines what's included in the VPO container
base: python:3.12-slim

packages:
  - ffmpeg
  - ffprobe
  - mkvpropedit
  - mkvmerge

python_package: video-policy-orchestrator

entrypoint: vpo
```

## No Schema Changes

This feature does not modify:
- SQLite database schema
- Policy YAML schema
- Plugin interface contracts
- CLI argument structure

All existing schemas remain unchanged.
