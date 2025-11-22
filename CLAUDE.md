# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Video Policy Orchestrator (VPO) is a spec-driven tool for scanning, organizing, and transforming video libraries using user-defined policies and an extensible plugin architecture. The project is in early development (pre-implementation).

## Development Methodology

This project uses **spec-driven development**:
1. Features start as specs in `docs/PRD.md` and `docs/ARCHITECTURE.md`
2. Detailed module specs live in `spec/`
3. Implementation follows specs with test-driven development

Use the Specify workflow commands (`/speckit.*`) for feature planning and implementation.

## Tech Stack (Planned)

- **Language:** Python
- **Database:** SQLite
- **External Tools:** ffmpeg/ffprobe, mkvmerge/mkvpropedit
- **Packaging:** pyproject.toml-based

## Architecture (Planned)

Key components:
- **CLI Frontend** - Commands: scan, inspect, apply, jobs, profiles
- **Core Engine** - Orchestrates scanning, policy evaluation, job scheduling, plugin calls
- **Media Introspector** - Wraps ffprobe/mkvmerge into uniform data model
- **Policy Engine** - Reads YAML/JSON policies, produces execution plans
- **Execution Layer & Job Queue** - Handles metadata edits, remuxes, transcodes, file moves
- **Plugin System** - Analyzer, Mutator, and Transcription plugins
