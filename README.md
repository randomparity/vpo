# Video Policy Orchestrator (working title)

> **Goal:** A spec-driven tool for scanning, organizing, and transforming video libraries using user-defined policies and an extensible plugin architecture.

---

## Overview

Video Policy Orchestrator (VPO) is a software application that analyzes video files (e.g. `*.mkv`, `*.mp4`) and applies user-defined **policies** to:

- Normalize and reorder tracks (video, audio, subtitles)
- Standardize audio track ordering and metadata
- Detect and tag audio track languages via transcription
- Optionally recompress video using selected codecs and quality settings
- Maintain a database of scanned files and actions
- Move or rename files based on discovered metadata
- Extend behavior via a **plugin system** (analyzers, mutators, transcribers, etc.)

The project is developed using **Claude Code** and a **GitHub spec-driven methodology**: behavior is first described in specs (PRDs, design docs), and then implemented with AI-assisted but test-driven development.

---

## Motivation

Modern media libraries often contain:

- Inconsistent track ordering and metadata
- Multiple audio formats with unclear priorities
- Incorrect or missing language tags
- Commentary tracks mixed in with main audio
- Mixed codecs, bitrates, and resolutions
- Directory structures that don’t reflect actual content

Most tools focus on low-level editing (`ffmpeg`, `mkvmerge`, etc.), leaving users to script ad-hoc workflows themselves.

**VPO** aims to act as the **policy layer** on top of existing media tools:

- You define *what you want* your library to look like.
- The tool figures out *how to get there* and keeps it that way over time.

---

## Core Capabilities (Planned)

### 1. Library Scanning & Database

- Recursively scan directories for supported video containers.
- Extract container and track metadata via external tools (e.g. `ffprobe`, `mkvmerge`).
- Store results in a local database (initially SQLite) for:
  - Incremental rescans
  - Job tracking and history
  - Policy versioning

### 2. Policy-Driven Track Organization

- Define policies in human-readable config (e.g. YAML/JSON), such as:
  - Track order: video → primary audio → alternate audio → subtitles → commentary.
  - Audio preferences: e.g. “Dolby 5.1 EAC first, AAC second, preserve DTS-HD, commentary last”.
  - Subtitle ordering and default tracks.
- Run in **dry-run** mode to see proposed changes before modifying files.
- Apply **metadata-only** changes where possible:
  - Default flags, language codes, titles, track ordering, tags.

### 3. Audio Transcription & Language Detection

- Optional transcription plugins (e.g. Whisper) to:
  - Detect spoken language for each audio track.
  - Update track metadata to reflect actual language.
- Heuristics for identifying commentary or alt tracks:
  - Based on metadata, language, and transcription content.
  - Allow commentary tracks to be moved to the end and clearly marked.

### 4. Transcoding & File Movement (Optional)

- Policies for recompressing video tracks:
  - Target codec (e.g. H.265 / AV1).
  - Quality settings (CRF, bitrate, resolution caps).
- Preserve or downmix audio formats according to user rules.
- Move or rename files based on metadata (e.g. title, year, resolution, language).
- Maintain a **job system** to track long-running operations (transcode, move, etc.).

### 5. Plugin Architecture

- Core is intentionally small; most specialized behavior lives in plugins.
- Plugin types (planned):
  - **Analyzer plugins** – enrich metadata, perform checks, tag content.
  - **Mutator plugins** – modify containers, rewrite metadata, move files.
  - **Transcription plugins** – provide speech-to-text and language detection.
- Plugin discovery via:
  - Configurable plugin directories, and/or
  - Python entry points (for packaged plugins).
- A small “plugin SDK” with helpers and templates for plugin authors.

---

## Architecture at a Glance

High-level components (subject to refinement):

- **CLI Frontend**
  - Commands like `scan`, `inspect`, `apply`, `jobs`, `profiles`.
  - Human-friendly output plus machine-readable modes where useful.

- **Core Engine**
  - Orchestrates scanning, policy evaluation, job scheduling, and plugin calls.
  - Exposes stable internal interfaces used by plugins.

- **Media Introspector**
  - Abstracts external tools (e.g. `ffprobe`, `mkvmerge`) into a uniform data model.
  - Handles container/track parsing and error handling.

- **Policy Engine**
  - Reads policy files and the current DB state.
  - Produces a **plan**: an abstract description of the desired final state.
  - The plan is later executed by mutators / plugins.

- **Execution Layer & Job Queue**
  - Executes operations (metadata edits, remuxes, transcodes, moves).
  - Records history and status to the DB for observability.

- **Database**
  - Tracks files, tracks, policies, jobs, and operation history.
  - Enables incremental scanning and auditability.

- **Plugin System**
  - Discovers, registers, and runs plugins.
  - Provides a clear API boundary and versioning strategy.

---

## Development Approach

This project is built around **spec-driven development** and **Claude Code**:

1. **Specify First**
   - New features start as updates to:
     - `docs/PRD.md` – Product requirements and user stories.
     - `docs/ARCHITECTURE.md` – Design details and diagrams.
     - `spec/` – More detailed specs for modules, types, and behaviors.
2. **Review & Iterate**
   - Specs are reviewed and refined before implementation.
3. **AI-Assisted Implementation**
   - Claude Code is used to generate and refine code, tests, and docs based on the specs.
4. **Test & Integrate**
   - Unit and integration tests validate behavior.
   - CI runs on every PR to keep the main branch healthy.

Over time, the specs will become the canonical source of truth for both humans and AI agents collaborating on this repository.

---

## Planned Roadmap (High Level)

The initial roadmap will be implemented across a series of sprints (subject to change):

1. **Sprint 0 – Project Inception**
   - Repo scaffold, tooling, initial PRD/architecture docs.

2. **Sprint 1 – Scanning & DB Foundation**
   - Directory scanning, initial DB schema, basic introspection stubs.

3. **Sprint 2 – Track Modeling**
   - Full track enumeration and metadata storage.

4. **Sprint 3 – Policy Engine & Reordering (Dry-Run & Metadata-Only)**
   - Policy format, dry runs, metadata edits, safety features.

5. **Sprint 4 – Plugin Architecture**
   - Plugin interfaces, discovery, and reference plugins.

6. **Sprint 5 – Transcoding & File Movement**
   - Job system, recompression policies, move/rename rules.

7. **Sprint 6 – Transcription & Language Detection**
   - Transcriber plugins, language tagging, commentary detection.

8. **Sprint 7+ – UX, Scheduling, Packaging**
   - Incremental scans, config profiles, docs, packaging (PyPI, containers).

Details for each sprint will live in the `docs/` and `spec/` directories and be tracked via GitHub issues/projects.

---

## Tech Stack (Tentative)

- **Language:** Python
- **DB:** SQLite (initially), with a clean abstraction for possible future backends
- **External Tools:** `ffmpeg` / `ffprobe`, `mkvmerge` / `mkvpropedit`, etc.
- **Packaging:** `pyproject.toml`-based Python package; optional container image
- **CI:** GitHub Actions (lint, test, type-check)

These choices are subject to change as the project evolves, but the README reflects the initial direction.

---

## Contributing

At this early stage, the project is still defining its core specs and architecture.

- Start by reading:
  - `README.md` (this file)
  - `docs/PRD.md` (once created)
  - `docs/ARCHITECTURE.md` (once created)
- Open an issue for:
  - New feature ideas
  - Policy use cases you care about
  - Plugin concepts you’d like to see supported
- Pull requests should:
  - Update relevant specs first (if behavior changes)
  - Include tests for new or changed behavior

Guidelines for coding style, commit conventions, and branch strategy will be documented in `CONTRIBUTING.md` as the project matures.

---

## License

License is **TBD** for the initial commit.
Once chosen, the license information and `LICENSE` file will be added here.
