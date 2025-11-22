# Project Overview

**Purpose:**
This document provides a high-level overview of Video Policy Orchestrator (VPO), including its goals, core use cases, target users, and project roadmap.

---

## What is VPO?

Video Policy Orchestrator (VPO) is a spec-driven tool for scanning, organizing, and transforming video libraries using user-defined policies and an extensible plugin architecture.

VPO acts as a **policy layer** on top of existing media tools (ffmpeg, mkvmerge, etc.):
- You define *what you want* your library to look like
- The tool figures out *how to get there* and keeps it that way over time

---

## Core Use Cases

### 1. Library Scanning & Database

Recursively scan directories for supported video containers and extract metadata:
- Scan directories for `*.mkv`, `*.mp4`, and other supported formats
- Extract container and track metadata via external tools (ffprobe, mkvmerge)
- Store results in a local SQLite database for incremental rescans, job tracking, and policy versioning

### 2. Policy-Driven Track Organization

Define policies in human-readable config (YAML/JSON) to:
- **Normalize track order**: video → primary audio → alternate audio → subtitles → commentary
- **Set audio preferences**: e.g., "Dolby 5.1 EAC first, AAC second, preserve DTS-HD, commentary last"
- **Configure subtitle ordering** and default tracks
- **Run in dry-run mode** to preview changes before modifying files
- **Apply metadata-only changes** where possible (default flags, language codes, titles, track ordering)

### 3. Audio Transcription & Language Detection

Optional transcription plugins (e.g., Whisper) to:
- Detect spoken language for each audio track
- Update track metadata to reflect actual language
- Identify commentary or alternate tracks via heuristics
- Move commentary tracks to the end with clear marking

### 4. Transcoding & File Movement

Policies for video transformation:
- **Recompress video** with target codec (H.265, AV1), quality settings (CRF, bitrate, resolution caps)
- **Preserve or downmix audio** according to user rules
- **Move or rename files** based on metadata (title, year, resolution, language)
- **Job system** to track long-running operations

### 5. Plugin Extensions

Extensible via plugins:
- **Analyzer plugins**: enrich metadata, perform checks, tag content
- **Mutator plugins**: modify containers, rewrite metadata, move files
- **Transcription plugins**: speech-to-text and language detection

---

## Target Users

- **Media enthusiasts** with large video libraries needing organization
- **Home server administrators** maintaining Plex, Jellyfin, or similar media servers
- **Content curators** who need consistent metadata and track ordering
- **Power users** comfortable with configuration files and CLI tools

---

## Success Metrics

- Zero data loss during operations
- Dry-run mode accurately predicts all changes
- Policy application is idempotent (running twice produces same result)
- CI feedback within 5 minutes
- Plugin API is stable and well-documented

---

## Roadmap

| Sprint | Focus | Key Deliverables |
|--------|-------|------------------|
| 0 | Project Inception | Repo scaffold, tooling, PRD/architecture docs |
| 1 | Scanning & DB Foundation | Directory scanning, DB schema, introspection stubs |
| 2 | Track Modeling | Track enumeration and metadata storage |
| 3 | Policy Engine | Policy format, dry runs, metadata edits |
| 4 | Plugin Architecture | Plugin interfaces, discovery, reference plugins |
| 5 | Transcoding & Movement | Job system, recompression, move/rename |
| 6 | Transcription | Transcriber plugins, language detection |
| 7+ | UX & Packaging | Config profiles, docs, PyPI, containers |

---

## Out of Scope (Initial Release)

- GUI interface (CLI only)
- Cloud storage integration
- Real-time file monitoring
- Multi-user collaboration features

---

## Related docs

- [Documentation Index](../INDEX.md)
- [Architecture Overview](architecture.md)
- [Data Model](data-model.md)
- [CLI Usage](../usage/cli-usage.md) *(planned)*
