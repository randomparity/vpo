# Research: Polish, Packaging, and Plugin Ecosystem Readiness

**Feature Branch**: `009-polish-packaging-plugins`
**Date**: 2025-11-22

## R1: PyPI Publishing with Rust Extensions (maturin)

### Decision
Use maturin with GitHub Actions for building platform-specific wheels.

### Rationale
- maturin is already configured in `pyproject.toml` as the build backend
- GitHub Actions provides free CI for open source with matrix builds
- maturin-action is the official GitHub Action maintained by PyO3 team
- Supports building wheels for multiple platforms in parallel

### Implementation Details

```yaml
# release.yml workflow structure
jobs:
  build:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-13, macos-14]  # Linux, macOS Intel, macOS ARM
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: PyO3/maturin-action@v1
        with:
          command: build
          args: --release --strip
```

### Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| cibuildwheel | Designed for pure-Python wheels; maturin handles Rust better |
| Manual wheel building | Error-prone, not reproducible |
| Conda packaging | Additional complexity, smaller user base than PyPI |

---

## R2: Container Image Strategy

### Decision
Multi-stage Dockerfile based on Python slim with ffmpeg and mkvtoolnix.

### Rationale
- Existing `docker/ffmpeg/` provides build patterns for ffmpeg
- Python slim base (~50MB) is smaller than full Python image (~900MB)
- Multi-stage build keeps final image lean
- GitHub Container Registry (ghcr.io) is free for public repos

### Size Budget

| Component | Estimated Size |
|-----------|---------------|
| Python 3.12-slim | ~50MB |
| ffmpeg + ffprobe | ~150MB |
| mkvtoolnix | ~50MB |
| VPO + dependencies | ~50MB |
| **Total** | ~300-350MB |

### Implementation Details

```dockerfile
# Stage 1: Build
FROM python:3.12-slim AS builder
RUN pip install maturin
COPY . /app
RUN cd /app && maturin build --release

# Stage 2: Runtime
FROM python:3.12-slim
RUN apt-get update && apt-get install -y ffmpeg mkvtoolnix
COPY --from=builder /app/target/wheels/*.whl /tmp/
RUN pip install /tmp/*.whl
```

### Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Alpine base | musl libc compatibility issues with Python/Rust |
| Ubuntu base | Larger image size (~200MB base) |
| Distroless | No shell for debugging, harder to customize |

---

## R3: Tutorial Documentation Approach

### Decision
Single `docs/tutorial.md` covering the complete user journey.

### Rationale
- New users want one document to follow, not scattered pages
- Matches natural workflow: install → scan → inspect → policy → apply
- Users supply own video files (per spec clarification)
- Each section is standalone but builds progressively

### Structure

1. **Prerequisites** - ffmpeg, Python 3.10+
2. **Installation** - pip install from PyPI
3. **First Scan** - Scan a directory, view results
4. **Inspect Files** - Examine individual file details
5. **Create Policy** - Write a simple YAML policy
6. **Apply Policy** - Dry-run, then apply
7. **Next Steps** - Links to advanced docs

### User's Video Files
Per clarification, tutorial will specify:
- Supported formats: MKV, MP4 recommended
- Multi-track files work best (video + 2+ audio or subtitles)
- Any personal video library files will work

---

## R4: Plugin Author Guide vs Existing Documentation

### Decision
Create separate `docs/plugin-author-guide.md` focused on development workflow.

### Rationale
- Existing `docs/plugins.md` (311 lines) is comprehensive API reference
- New guide targets different audience: developers building plugins
- Focus areas: project setup, testing, packaging, publishing
- Minimal overlap with existing content

### Content Comparison

| docs/plugins.md (existing) | docs/plugin-author-guide.md (new) |
|---------------------------|-----------------------------------|
| API reference | Development workflow |
| Event types | Project structure |
| Base classes | Testing strategies |
| CLI commands | Packaging for PyPI |
| Security model | Publishing checklist |

### Hello World Template
Create `examples/plugins/hello_world/` as minimal starting point:
- Single Python file plugin
- pyproject.toml with entry point
- Basic tests
- README with instructions

Distinct from `simple_reorder_plugin/` which is a more complete example.

---

## R5: Roadmap and Backlog Organization

### Decision
GitHub Issues with labels + README.md Roadmap section.

### Rationale
- GitHub Issues enables community tracking and contributions
- README Roadmap provides quick visibility
- Labels organize without complex project boards

### Label Schema

| Label | Purpose |
|-------|---------|
| `epic` | Major feature grouping |
| `good-first-issue` | Suitable for new contributors |
| `help-wanted` | Community contributions welcome |
| `priority:high` | Critical for next release |
| `priority:medium` | Important but not blocking |
| `priority:low` | Nice to have |
| `type:feature` | New functionality |
| `type:bug` | Defect fix |
| `type:docs` | Documentation improvement |

### Roadmap Epics (Draft)

1. **Windows Support** - Pre-built wheels, CI testing
2. **GPU Transcoding** - NVENC/VAAPI acceleration
3. **Web UI** - Browser-based library management
4. **Batch Reporting** - Summary reports for policy runs
5. **Watch Mode** - Automatic processing of new files

---

## Research Complete

All unknowns resolved. Ready for Phase 1 design artifacts.
