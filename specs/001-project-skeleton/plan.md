# Implementation Plan: Project Skeleton Setup

**Branch**: `001-project-skeleton` | **Date**: 2025-11-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-project-skeleton/spec.md`

## Summary

Establish the foundational project infrastructure for Video Policy Orchestrator (VPO), including a Python package skeleton with src layout, development tooling (ruff, pytest), CI pipeline via GitHub Actions, and initial documentation (PRD, ARCHITECTURE, CONTRIBUTING). This enables subsequent feature development with consistent style, testing, and quality gates.

## Technical Context

**Language/Version**: Python 3.10+ (minimum supported; CI will test 3.10, 3.11, 3.12)
**Primary Dependencies**: ruff (linting/formatting), pytest (testing)
**Storage**: N/A (infrastructure sprint, no data persistence)
**Testing**: pytest with src layout discovery
**Target Platform**: Cross-platform (Linux, macOS, Windows) via Python
**Project Type**: Single Python package with src layout
**Performance Goals**: N/A (infrastructure sprint)
**Constraints**: CI feedback within 5 minutes; zero linting errors on setup
**Scale/Scope**: Minimal viable skeleton; single package, ~5 source files, ~10 config/doc files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Status**: Constitution not yet established (Sprint 0 precedes constitution setup)

Since this is Sprint 0 (Project Inception), the constitution file contains only template placeholders. The constitution will be defined as part of the project's ongoing setup. For this sprint:

- **Library-First**: N/A - establishing package structure, not feature libraries
- **CLI Interface**: N/A - no CLI in this sprint
- **Test-First**: Will establish pytest infrastructure; no feature tests yet
- **Integration Testing**: N/A - infrastructure only
- **Simplicity**: PASS - minimal skeleton with only essential tooling

**Gate Result**: PASS (constitution not yet applicable; sprint establishes foundation)

## Project Structure

### Documentation (this feature)

```text
specs/001-project-skeleton/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (minimal for infra sprint)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (empty for infra sprint)
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
# Single Python package with src layout
src/
└── vpo/
    └── __init__.py      # Package entry point with version

tests/
└── test_package.py      # Minimal package import test

# Configuration files
pyproject.toml           # Package config, ruff, pytest settings
Makefile                 # Common dev commands (test, lint, format)

# CI/CD
.github/
└── workflows/
    └── ci.yml           # Lint + test workflow

# Documentation
docs/
├── PRD.md               # Product requirements document
└── ARCHITECTURE.md      # System architecture

CONTRIBUTING.md          # Contribution guidelines
README.md                # Already exists - no changes needed
CLAUDE.md                # Already exists - no changes needed
```

**Structure Decision**: Single Python package using src layout (PEP 517/518 compliant). The src/ directory prevents accidental imports of uninstalled code. Tests live in a separate tests/ directory at root level for pytest auto-discovery.

## Complexity Tracking

No complexity violations. This sprint establishes the minimal viable skeleton with only essential tooling (ruff + pytest). No additional frameworks, patterns, or abstractions introduced.
