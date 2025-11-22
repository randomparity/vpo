# Tasks: Project Skeleton Setup

**Input**: Design documents from `/specs/001-project-skeleton/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, quickstart.md

**Tests**: Not explicitly requested in feature specification. Minimal verification test included for package import.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root (per plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create directory structure and basic project skeleton

- [X] T001 Create src/video_policy_orchestrator/ directory structure
- [X] T002 Create tests/ directory at repository root
- [X] T003 [P] Create docs/ directory at repository root
- [X] T004 [P] Create .github/workflows/ directory structure

**Checkpoint**: Directory structure ready for file creation

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core configuration that MUST be complete before user stories can be validated

**Note**: For this infrastructure sprint, there are no blocking prerequisites. User stories can proceed after directory setup.

**Checkpoint**: Foundation ready - user story implementation can begin

---

## Phase 3: User Story 1 - Python Package Setup (Priority: P1) MVP

**Goal**: Create a properly configured Python package with tooling (ruff/pytest) so developers can iterate quickly with consistent style and tests.

**Independent Test**: Clone repo, run `pip install -e ".[dev]"`, then `pytest` and `ruff check .` both pass.

### Implementation for User Story 1

- [X] T005 [US1] Create pyproject.toml with package metadata at repository root (name: video-policy-orchestrator, version: 0.1.0, requires-python: >=3.10)
- [X] T006 [US1] Add [project.optional-dependencies] dev section with ruff and pytest in pyproject.toml
- [X] T007 [US1] Add [tool.ruff] configuration section in pyproject.toml (target-version: py310, line-length: 88)
- [X] T008 [US1] Add [tool.pytest.ini_options] configuration section in pyproject.toml (testpaths: ["tests"])
- [X] T009 [US1] Add [build-system] section in pyproject.toml (requires: setuptools, build-backend: setuptools.build_meta)
- [X] T010 [US1] Create src/video_policy_orchestrator/__init__.py with __version__ = "0.1.0"
- [X] T011 [US1] Create tests/test_package.py with minimal import test (assert package imports successfully)
- [X] T012 [US1] Create Makefile with targets: help, test, lint, format, clean at repository root
- [X] T013 [US1] Verify: run `pip install -e ".[dev]"` succeeds
- [X] T014 [US1] Verify: run `pytest` passes
- [X] T015 [US1] Verify: run `ruff check .` passes with zero errors

**Checkpoint**: User Story 1 complete - package installs and all tooling works

---

## Phase 4: User Story 2 - CI Integration (Priority: P2)

**Goal**: Create CI pipeline that runs linters and tests on every PR so regressions are caught automatically.

**Independent Test**: Push branch to GitHub, verify GitHub Actions runs and shows pass/fail status.

### Implementation for User Story 2

- [X] T016 [US2] Create .github/workflows/ci.yml with workflow name and triggers (push to main, pull_request)
- [X] T017 [US2] Add Python version matrix (3.10, 3.11, 3.12) and ubuntu-latest runner in ci.yml
- [X] T018 [US2] Add checkout action and Python setup action with caching in ci.yml
- [X] T019 [US2] Add lint job that runs `pip install -e ".[dev]"` and `ruff check .` in ci.yml
- [X] T020 [US2] Add test job that runs `pip install -e ".[dev]"` and `pytest` in ci.yml
- [ ] T021 [US2] Verify: push branch and confirm CI workflow runs successfully on GitHub

**Checkpoint**: User Story 2 complete - CI validates code on every PR

---

## Phase 5: User Story 3 - Documentation Foundation (Priority: P3)

**Goal**: Create PRD.md and ARCHITECTURE.md so agents and humans can understand the project's purpose and design.

**Independent Test**: Read docs/ folder contents and verify they explain core use cases and system architecture.

### Implementation for User Story 3

- [X] T022 [P] [US3] Create docs/PRD.md with sections: Overview, Core Use Cases, Target Users, Success Metrics, Roadmap
- [X] T023 [P] [US3] Create docs/ARCHITECTURE.md with sections: Overview, Component Diagram, Component Descriptions, Data Flow, External Dependencies
- [X] T024 [US3] Populate docs/PRD.md with content from README.md (scanning, policy application, database, plugins use cases)
- [X] T025 [US3] Populate docs/ARCHITECTURE.md with component list (CLI Frontend, Core Engine, Media Introspector, Policy Engine, Execution Layer, Plugin System, Database)
- [X] T026 [US3] Add ASCII or Mermaid diagram to docs/ARCHITECTURE.md showing component relationships
- [X] T027 [US3] Verify: docs/PRD.md covers all core use cases from README.md
- [X] T028 [US3] Verify: docs/ARCHITECTURE.md has component list and structure diagram

**Checkpoint**: User Story 3 complete - project purpose and architecture documented

---

## Phase 6: User Story 4 - Contributing Guidelines (Priority: P4)

**Goal**: Create CONTRIBUTING.md so contributors understand how to participate in the project effectively.

**Independent Test**: Read CONTRIBUTING.md and verify it explains development setup, coding standards, and PR process.

### Implementation for User Story 4

- [X] T029 [US4] Create CONTRIBUTING.md at repository root with sections: Getting Started, Development Setup, Code Style, Pull Request Process, Code Review
- [X] T030 [US4] Add Getting Started section with prerequisites (Python 3.10+, pip, git)
- [X] T031 [US4] Add Development Setup section with clone, venv, and pip install instructions
- [X] T032 [US4] Add Code Style section referencing ruff configuration in pyproject.toml
- [X] T033 [US4] Add Pull Request Process section with branch naming, commit conventions, PR template guidance
- [X] T034 [US4] Add Code Review section with review criteria and approval requirements
- [X] T035 [US4] Verify: CONTRIBUTING.md explains development workflow, coding standards, and PR process

**Checkpoint**: User Story 4 complete - contribution guidelines documented

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [X] T036 Run quickstart.md validation: follow all setup steps and verify they work
- [X] T037 Verify all linting passes: `ruff check .` returns zero errors
- [X] T038 Verify all tests pass: `pytest` returns zero failures
- [ ] T039 Verify CI passes on feature branch before merging
- [X] T040 Review all files for consistency (naming, formatting, structure)

**Checkpoint**: Sprint 0 complete - project skeleton ready for Sprint 1

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - minimal for this sprint
- **User Story 1 (Phase 3)**: Depends on Phase 1 directories
- **User Story 2 (Phase 4)**: Depends on Phase 3 (needs pyproject.toml and tests/)
- **User Story 3 (Phase 5)**: Depends on Phase 1 (needs docs/ directory)
- **User Story 4 (Phase 6)**: Depends on Phase 3 (references pyproject.toml tooling)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1 (Setup)
    │
    ├──► US1 (Package Setup) ──► US2 (CI Integration)
    │                               │
    │                               ▼
    │                          US4 (Contributing)
    │
    └──► US3 (Documentation) ─────────────────────────► Phase 7 (Polish)
```

- **User Story 1 (P1)**: Can start after Setup - BLOCKING for US2 and US4
- **User Story 2 (P2)**: Requires US1 complete (needs package to test)
- **User Story 3 (P3)**: Can start after Setup - PARALLEL with US1
- **User Story 4 (P4)**: Requires US1 complete (references tooling)

### Within Each User Story

- Configuration before source files
- Source files before verification
- Verification at end of each story

### Parallel Opportunities

Within Phase 1:
- T003 and T004 can run in parallel (different directories)

Within User Story 3:
- T022 and T023 can run in parallel (different files)

Across User Stories:
- US1 and US3 can run in parallel after Phase 1

---

## Parallel Example: Phase 1 Setup

```bash
# Launch directory creation in parallel:
Task: "Create docs/ directory at repository root"
Task: "Create .github/workflows/ directory structure"
```

## Parallel Example: User Story 3

```bash
# Launch documentation files in parallel:
Task: "Create docs/PRD.md with sections"
Task: "Create docs/ARCHITECTURE.md with sections"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (create directories)
2. Complete Phase 3: User Story 1 (package setup)
3. **STOP and VALIDATE**: Run `pip install -e ".[dev]"`, `pytest`, `ruff check .`
4. Package is usable for development

### Incremental Delivery

1. Complete Setup → Directories exist
2. Add User Story 1 → Package installable and testable (MVP!)
3. Add User Story 2 → CI validates PRs automatically
4. Add User Story 3 → Project documented for onboarding
5. Add User Story 4 → Contributors have guidelines
6. Each story adds value without breaking previous stories

### Recommended Execution Order

For single developer (sequential):
1. Phase 1 → Phase 3 (US1) → Phase 4 (US2) → Phase 5 (US3) → Phase 6 (US4) → Phase 7

For parallel work:
1. Phase 1 (both developers)
2. Developer A: US1 → US2 → US4
3. Developer B: US3
4. Phase 7 (both developers)

---

## Task Summary

| Phase | User Story | Task Count | Parallel Tasks |
|-------|------------|------------|----------------|
| 1 | Setup | 4 | 2 |
| 2 | Foundational | 0 | 0 |
| 3 | US1 - Package Setup | 11 | 0 |
| 4 | US2 - CI Integration | 6 | 0 |
| 5 | US3 - Documentation | 7 | 2 |
| 6 | US4 - Contributing | 7 | 0 |
| 7 | Polish | 5 | 0 |
| **Total** | | **40** | **4** |

---

## Notes

- [P] tasks = different files, no dependencies within phase
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- MVP = User Story 1 only (functional Python package with tooling)
