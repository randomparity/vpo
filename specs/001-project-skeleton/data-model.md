# Data Model: Project Skeleton Setup

**Feature**: 001-project-skeleton
**Date**: 2025-11-21

## Overview

This is an infrastructure sprint establishing project skeleton and tooling. No application data models are defined in this phase.

## Entities

### Package Metadata

The only "data" in this sprint is package metadata defined in pyproject.toml:

| Field | Type | Description |
|-------|------|-------------|
| name | string | Package name: "video-policy-orchestrator" |
| version | string | Semantic version starting at "0.1.0" |
| description | string | Brief package description |
| requires-python | string | Minimum Python version: ">=3.10" |
| authors | list | Package maintainers |
| license | string | Project license (TBD) |

### Configuration Files

| File | Purpose | Format |
|------|---------|--------|
| pyproject.toml | Package config, tool settings | TOML |
| .github/workflows/ci.yml | CI pipeline definition | YAML |
| Makefile | Development commands | Make |

## Relationships

```text
pyproject.toml
├── defines → package metadata
├── configures → ruff (linting)
├── configures → pytest (testing)
└── specifies → dependencies

.github/workflows/ci.yml
├── triggers on → push, pull_request
├── runs → ruff check
└── runs → pytest
```

## State Transitions

N/A - No stateful entities in this infrastructure sprint.

## Validation Rules

| Rule | Applies To | Constraint |
|------|-----------|------------|
| Valid TOML | pyproject.toml | Must parse without errors |
| Valid YAML | ci.yml | Must parse without errors |
| Package installable | pyproject.toml | `pip install -e .` succeeds |
| Tests pass | test suite | Exit code 0 from pytest |
| Lint passes | source code | Exit code 0 from ruff check |

## Future Data Models

The following entities will be defined in subsequent sprints:

- **MediaFile**: Video file with path, hash, metadata (Sprint 1)
- **Track**: Audio/video/subtitle track within a container (Sprint 2)
- **Policy**: User-defined rules for track organization (Sprint 3)
- **Job**: Queued operation for transcoding/moving (Sprint 5)

These are documented here for context but are out of scope for Sprint 0.
