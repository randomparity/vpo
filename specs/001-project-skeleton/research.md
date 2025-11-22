# Research: Project Skeleton Setup

**Feature**: 001-project-skeleton
**Date**: 2025-11-21

## Overview

This document captures research decisions for establishing the VPO project skeleton. Since this is an infrastructure sprint with well-established Python ecosystem conventions, research focuses on best practices rather than unknowns.

---

## Research Topics

### 1. Python Package Layout

**Decision**: Use `src/` layout (src/video_policy_orchestrator/)

**Rationale**:
- Prevents accidental imports of development code before installation
- PEP 517/518 compliant and recommended by PyPA
- Works correctly with editable installs (`pip install -e .`)
- Ensures tests run against the installed package, not source directory

**Alternatives Considered**:
- Flat layout (package at root): Rejected - can lead to import confusion during development
- Namespace packages: Rejected - unnecessary complexity for single-package project

---

### 2. Linting and Formatting Tool

**Decision**: Use ruff for both linting and formatting

**Rationale**:
- 10-100x faster than flake8/black/isort combined
- Single tool replaces flake8, isort, pyupgrade, and can format
- Active development with excellent Python 3.10+ support
- Compatible with existing black formatting conventions

**Alternatives Considered**:
- black + flake8 + isort: Rejected - three tools vs one, slower
- pylint: Rejected - slower, more opinionated, steeper learning curve
- mypy (type checking): Deferred to future sprint when types are added

---

### 3. Test Framework

**Decision**: Use pytest

**Rationale**:
- De facto standard for Python testing
- Simple test discovery with minimal boilerplate
- Excellent fixture system for future test setup needs
- Rich plugin ecosystem (pytest-cov, pytest-xdist, etc.)

**Alternatives Considered**:
- unittest: Rejected - more verbose, less flexible fixtures
- nose2: Rejected - less active community, pytest is dominant

---

### 4. Python Version Support

**Decision**: Python 3.10+ minimum, CI tests 3.10, 3.11, 3.12

**Rationale**:
- Python 3.10 provides structural pattern matching, improved type hints
- Python 3.9 EOL is October 2025, 3.10 EOL is October 2026
- Supporting three versions balances compatibility with maintenance burden
- Most dependencies support 3.10+

**Alternatives Considered**:
- Python 3.9+: Rejected - EOL imminent, modern features unavailable
- Python 3.12 only: Rejected - limits adoption, unnecessary restriction

---

### 5. CI Platform

**Decision**: GitHub Actions

**Rationale**:
- Native integration with GitHub repository
- Free for open source projects
- Extensive marketplace of actions
- Matrix builds for multiple Python versions

**Alternatives Considered**:
- CircleCI: Rejected - external service, more setup
- Jenkins: Rejected - requires self-hosting
- GitLab CI: Rejected - repository is on GitHub

---

### 6. Build System

**Decision**: pyproject.toml with setuptools backend

**Rationale**:
- PEP 517/518/621 compliant
- Single file for project metadata, dependencies, and tool config
- setuptools is stable and widely supported
- No need for poetry/flit complexity for simple package

**Alternatives Considered**:
- setup.py + setup.cfg: Rejected - legacy approach, pyproject.toml preferred
- poetry: Rejected - adds lock file complexity, overkill for this project
- flit: Rejected - less flexible than setuptools for future needs
- hatch: Considered - good alternative, but setuptools is more established

---

### 7. Makefile vs Task Runners

**Decision**: Simple Makefile with common targets

**Rationale**:
- Universally available on Unix systems
- No additional dependencies
- Self-documenting with `make help`
- Sufficient for basic dev workflow

**Alternatives Considered**:
- just: Rejected - requires installation, Makefile sufficient
- invoke: Rejected - Python-based adds dependency
- npm scripts via package.json: Rejected - not a JS project

---

## Configuration Decisions

### pyproject.toml Structure

```toml
[project]
name = "video-policy-orchestrator"
requires-python = ">=3.10"
dependencies = []  # Runtime deps added as needed

[project.optional-dependencies]
dev = ["ruff", "pytest"]

[tool.ruff]
target-version = "py310"
line-length = 88

[tool.pytest.ini_options]
testpaths = ["tests"]
```

### GitHub Actions Workflow

- Trigger: push to main, pull requests
- Matrix: Python 3.10, 3.11, 3.12 on ubuntu-latest
- Jobs: lint (ruff check), test (pytest)
- Caching: pip cache for faster runs

---

## Open Questions (None)

All technical decisions resolved. No NEEDS CLARIFICATION items remain.

---

## References

- [PyPA Packaging Guide](https://packaging.python.org/en/latest/)
- [PEP 517 - Build system interface](https://peps.python.org/pep-0517/)
- [PEP 621 - Project metadata](https://peps.python.org/pep-0621/)
- [ruff documentation](https://docs.astral.sh/ruff/)
- [pytest documentation](https://docs.pytest.org/)
- [GitHub Actions Python workflow](https://docs.github.com/en/actions/automating-builds-and-tests/building-and-testing-python)
