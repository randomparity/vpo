# Quickstart Scenarios: Polish, Packaging, and Plugin Ecosystem Readiness

**Feature Branch**: `009-polish-packaging-plugins`
**Date**: 2025-11-22

## Overview

This document defines validation scenarios for each user story. Each scenario is independently testable and represents a complete user journey.

---

## Scenario 1: Fresh pip Install (US1 - P1)

**Goal**: Verify package installs cleanly from PyPI without requiring Rust toolchain.

### Prerequisites
- Clean Python 3.10+ virtual environment
- No Rust toolchain installed
- pip available

### Steps

```bash
# 1. Create clean environment
python -m venv test-env
source test-env/bin/activate  # or test-env\Scripts\activate on Windows

# 2. Verify no Rust (should fail or not find cargo)
cargo --version || echo "No Rust - good!"

# 3. Install from PyPI
pip install video-policy-orchestrator

# 4. Verify installation
vpo --version
vpo --help

# 5. Verify CLI commands available
vpo scan --help
vpo inspect --help
vpo apply --help
vpo doctor
```

### Expected Results
- [ ] pip install completes in under 2 minutes
- [ ] No compilation occurs (pre-built wheel used)
- [ ] `vpo --version` shows installed version
- [ ] `vpo --help` shows available commands
- [ ] `vpo doctor` runs (may show warnings about ffmpeg if not installed)

### Platforms to Test
- [ ] Linux x86_64 (Ubuntu 22.04)
- [ ] macOS arm64 (M1/M2/M3)
- [ ] macOS x86_64 (Intel)

---

## Scenario 2: End-to-End Tutorial (US2 - P2)

**Goal**: New user completes tutorial successfully within 30 minutes.

### Prerequisites
- VPO installed (via pip or development install)
- ffmpeg/ffprobe available
- At least one video file (MKV or MP4 with multiple tracks preferred)

### Steps

```bash
# 1. Scan a directory
vpo scan ~/Videos

# 2. Inspect a specific file
vpo inspect ~/Videos/movie.mkv

# 3. Create a simple policy (policy.yaml)
cat > policy.yaml << 'EOF'
name: my-first-policy
version: "1.0"
description: Reorder tracks by language preference

rules:
  audio:
    order_by:
      - language: eng
      - language: jpn
    default: first
EOF

# 4. Preview changes
vpo apply --policy policy.yaml ~/Videos/movie.mkv --dry-run

# 5. (Optional) Apply changes
# vpo apply --policy policy.yaml ~/Videos/movie.mkv
```

### Expected Results
- [ ] Tutorial document exists at docs/tutorial.md
- [ ] All commands in tutorial execute without errors
- [ ] User understands output of each command
- [ ] Policy YAML syntax is clear and correct
- [ ] Dry-run output explains planned changes
- [ ] Total time under 30 minutes for new user

---

## Scenario 3: Plugin Development (US3 - P3)

**Goal**: Developer creates working plugin within 1 hour using guide and template.

### Prerequisites
- Python development environment
- Familiarity with Python packaging

### Steps

```bash
# 1. Copy hello_world template
cp -r examples/plugins/hello_world ~/my-plugin
cd ~/my-plugin

# 2. Review plugin guide
# Read docs/plugin-author-guide.md

# 3. Customize plugin
# Edit src/my_plugin/__init__.py
# Change name, add custom logic

# 4. Install in development mode
pip install -e .

# 5. Verify plugin loads
vpo plugins list
# Should show "my-plugin" in list

# 6. Test plugin
vpo scan ~/Videos  # Plugin should receive events

# 7. Run plugin tests
pytest tests/
```

### Expected Results
- [ ] Plugin author guide exists at docs/plugin-author-guide.md
- [ ] Hello world template exists at examples/plugins/hello_world/
- [ ] Template passes ruff check (no lint errors)
- [ ] Template tests pass
- [ ] Plugin appears in `vpo plugins list`
- [ ] Plugin receives events during scan
- [ ] Developer completes process in under 1 hour

### Template Structure
```text
hello_world/
├── pyproject.toml      # Entry point configured
├── README.md           # Usage instructions
├── src/
│   └── hello_world/
│       └── __init__.py # Plugin implementation
└── tests/
    └── test_plugin.py  # Basic tests
```

---

## Scenario 4: Container Usage (US4 - P4)

**Goal**: User runs VPO via container without local Python/ffmpeg installation.

### Prerequisites
- Docker or Podman installed
- Video files in accessible directory

### Steps

```bash
# 1. Pull container image
docker pull ghcr.io/randomparity/vpo:latest

# 2. Run scan with volume mount
docker run --rm -v ~/Videos:/data ghcr.io/randomparity/vpo:latest scan /data

# 3. Inspect a file
docker run --rm -v ~/Videos:/data ghcr.io/randomparity/vpo:latest inspect /data/movie.mkv

# 4. Run doctor to verify tools
docker run --rm ghcr.io/randomparity/vpo:latest doctor

# 5. Check image size
docker images ghcr.io/randomparity/vpo:latest --format "{{.Size}}"
```

### Expected Results
- [ ] Container image pulls successfully
- [ ] Image size under 500MB
- [ ] Scan works with mounted volume
- [ ] Inspect shows file details
- [ ] `vpo doctor` shows all tools available (ffmpeg, mkvtoolnix)
- [ ] No permission issues with mounted files

### Container Usage Notes
- Default working directory: `/data`
- Mount video directory to `/data` for simplest paths
- Database persists in container (ephemeral unless volume mounted for `~/.vpo`)

---

## Scenario 5: Roadmap and Contribution (US5 - P5)

**Goal**: Contributor can understand project direction and find entry points.

### Prerequisites
- GitHub account
- Browser access to repository

### Steps

```bash
# 1. View README roadmap
# Open https://github.com/randomparity/vpo
# Scroll to Roadmap section

# 2. Browse issues
# Navigate to Issues tab
# Filter by label: good-first-issue

# 3. View project board (if exists)
# Navigate to Projects tab

# 4. Check issue labels
gh label list --repo randomparity/vpo
```

### Expected Results
- [ ] README.md contains Roadmap section
- [ ] Roadmap lists 3-5 future epics
- [ ] GitHub Issues exist for major features
- [ ] Labels include: `good-first-issue`, `help-wanted`, `epic`
- [ ] At least 2 issues labeled `good-first-issue`
- [ ] Issues are organized and have descriptions

### Issue Labels
| Label | Purpose |
|-------|---------|
| `epic` | Major feature grouping |
| `good-first-issue` | Suitable for new contributors |
| `help-wanted` | Community contributions welcome |
| `priority:high` | Critical for next release |
| `priority:medium` | Important but not blocking |
| `priority:low` | Nice to have |

---

## Validation Summary

| Scenario | User Story | Success Criteria |
|----------|------------|-----------------|
| Fresh pip install | US1 (P1) | Install < 2 min, no Rust needed |
| Tutorial completion | US2 (P2) | All commands work, < 30 min |
| Plugin development | US3 (P3) | Working plugin < 1 hour |
| Container usage | US4 (P4) | Image < 500MB, scan works |
| Roadmap visibility | US5 (P5) | Clear direction, entry points |

All scenarios must pass before feature is considered complete.
