# Implementation Plan: Polish, Packaging, and Plugin Ecosystem Readiness

**Branch**: `009-polish-packaging-plugins` | **Date**: 2025-11-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/009-polish-packaging-plugins/spec.md`

## Summary

Make VPO easy to install via PyPI and container images, provide comprehensive documentation for new users and plugin developers, and establish a project roadmap. This feature focuses on packaging automation, documentation, and community readiness rather than new functional capabilities.

## Technical Context

**Language/Version**: Python 3.10+ (existing), Rust (PyO3/maturin for extension)
**Primary Dependencies**: click, pydantic, PyYAML (existing); maturin (build), GitHub Actions (CI/CD)
**Storage**: N/A (no new storage requirements)
**Testing**: pytest (existing); manual installation testing on clean environments
**Target Platform**: Linux x86_64, macOS arm64, macOS x86_64 (Windows deferred)
**Project Type**: Single Python package with Rust extension
**Performance Goals**: Installation completes in under 2 minutes; container image under 500MB
**Constraints**: Pre-built wheels required to avoid Rust toolchain dependency for users
**Scale/Scope**: Documentation-heavy feature; ~5 new/updated docs, 2 new CI workflows

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| III. Portable Paths | PASS | No new path handling; existing pathlib usage maintained |
| XV. Stable CLI/API Contracts | PASS | No CLI changes; documenting existing stable interface |
| XVI. Dry-Run Default | N/A | No new operations that modify files |
| XVIII. Living Documentation | PASS | This feature creates/updates documentation |
| XI. Plugin Isolation | PASS | Documenting existing plugin interfaces, not changing them |

**Gate Result**: PASS - No violations. Feature is documentation and packaging focused.

## Project Structure

### Documentation (this feature)

```text
specs/009-polish-packaging-plugins/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (minimal - no new data models)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CI workflow contracts)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
# Existing structure - no changes to src/

.github/workflows/
├── ci.yml               # Existing CI (no changes)
├── release.yml          # NEW: PyPI release workflow
└── docker.yml           # NEW: Container image build/push

docs/
├── INDEX.md             # UPDATE: Add tutorial link
├── tutorial.md          # NEW: End-to-end getting started guide
├── plugins.md           # EXISTING: Already comprehensive
└── plugin-author-guide.md  # NEW: Developer-focused plugin guide

docker/
├── ffmpeg/              # EXISTING: ffmpeg-only container
└── vpo/                 # NEW: Full VPO container with all deps
    └── Dockerfile

examples/plugins/
├── simple_reorder_plugin/  # EXISTING: Complete example
└── hello_world/            # NEW: Minimal plugin template

README.md                # UPDATE: Add Roadmap section
```

**Structure Decision**: Using existing single-project structure. New files are documentation, CI workflows, and container configuration only.

## Complexity Tracking

> No violations - feature is documentation and packaging focused.

## Phase 0: Research Findings

### R1: PyPI Publishing with Rust Extensions

**Decision**: Use maturin with GitHub Actions for building platform wheels

**Rationale**:
- maturin is already configured in pyproject.toml
- GitHub Actions matrix builds can target Linux, macOS x86_64, and macOS arm64
- maturin-action handles cross-compilation and wheel building

**Alternatives Considered**:
- cibuildwheel: More complex, designed for pure-Python wheels
- Manual wheel building: Error-prone, not reproducible

### R2: Container Image Strategy

**Decision**: Multi-stage build based on Python slim image with ffmpeg/mkvtoolnix

**Rationale**:
- Existing docker/ffmpeg/ provides foundation
- Python slim base keeps image size reasonable
- Multi-stage build separates build dependencies from runtime

**Size Estimate**: ~350-450MB (Python slim ~50MB + ffmpeg ~200MB + mkvtoolnix ~50MB + VPO ~50MB)

### R3: Tutorial Approach

**Decision**: Single docs/tutorial.md covering install → scan → inspect → policy → apply

**Rationale**:
- Matches user journey from install to first successful policy application
- Users supply own video files (per clarification)
- Each section standalone but builds on previous

### R4: Plugin Author Guide vs Existing docs/plugins.md

**Decision**: Create separate docs/plugin-author-guide.md focused on development workflow

**Rationale**:
- Existing docs/plugins.md is comprehensive API reference
- New guide focuses on: project setup, testing, packaging, publishing
- Different audiences: users extending VPO vs developers building plugins

### R5: Roadmap Organization

**Decision**: GitHub Issues with labels + README.md Roadmap section

**Rationale**:
- GitHub Issues provides tracking and community engagement
- README Roadmap gives quick visibility without navigating to Issues
- Labels: `epic`, `good-first-issue`, `help-wanted`, `priority:high/medium/low`

## Phase 1: Design Artifacts

### 1.1 Data Model

This feature introduces no new data models. All work is documentation, CI configuration, and container setup.

See: [data-model.md](data-model.md)

### 1.2 Contracts

CI workflow contracts define the automation for packaging and distribution:

- `release.yml`: Triggered on version tags, builds wheels, publishes to PyPI
- `docker.yml`: Triggered on release, builds and pushes container image

See: [contracts/](contracts/)

### 1.3 Quickstart Scenarios

Key scenarios for validating this feature:

1. **Fresh pip install**: User installs from PyPI without Rust toolchain
2. **Tutorial completion**: New user follows tutorial end-to-end
3. **Plugin creation**: Developer creates plugin from template
4. **Container usage**: User runs VPO via container on video directory

See: [quickstart.md](quickstart.md)

## Implementation Phases

### Phase 1: PyPI Packaging (US1)
- Create release.yml workflow with maturin-action
- Test wheel builds on all target platforms
- Configure PyPI trusted publishing

### Phase 2: Tutorial Documentation (US2)
- Create docs/tutorial.md
- Update docs/INDEX.md with tutorial link
- Validate all commands work on fresh install

### Phase 3: Plugin Author Guide (US3)
- Create docs/plugin-author-guide.md
- Create examples/plugins/hello_world/ template
- Validate template passes lint/type checks

### Phase 4: Container Image (US4)
- Create docker/vpo/Dockerfile
- Create docker.yml workflow
- Test container with volume mount

### Phase 5: Roadmap & Backlog (US5)
- Create GitHub Issues for future epics
- Add Roadmap section to README.md
- Add issue labels and templates

## Next Steps

Run `/speckit.tasks` to generate detailed task breakdown with dependencies and estimates.
