# Tasks: Polish, Packaging, and Plugin Ecosystem Readiness

**Input**: Design documents from `/specs/009-polish-packaging-plugins/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: No test tasks included - this feature is documentation and CI/CD configuration focused.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**User Request**: Commit changes after each phase is complete.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: Using existing repository structure
- CI workflows: `.github/workflows/`
- Documentation: `docs/`
- Docker: `docker/`
- Examples: `examples/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new setup required - using existing project infrastructure

This feature adds to an existing project with established CI, documentation structure, and tooling. No setup phase tasks needed.

**Checkpoint**: Proceed directly to user story implementation.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data model extensions that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

This feature has no foundational blocking tasks - each user story is independently implementable using existing project infrastructure.

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Package Installation via pip (Priority: P1)

**Goal**: Enable users to install VPO via `pip install video-policy-orchestrator` with pre-built wheels for Linux and macOS.

**Independent Test**: Run `pip install video-policy-orchestrator` in a clean Python environment without Rust toolchain and verify `vpo --help` works.

### Implementation for User Story 1

- [x] T001 [P] [US1] Create release workflow for wheel building in .github/workflows/release.yml
- [x] T002 [P] [US1] Update pyproject.toml with PyPI metadata (description, classifiers, URLs, dependencies) in pyproject.toml
- [x] T002a [US1] Document installation fallback for unsupported platforms in README.md (requires Rust toolchain)
- [ ] T003 [US1] Configure PyPI trusted publishing in GitHub repository settings (manual step - document in PR)
- [x] T004 [US1] Test wheel build locally with `maturin build --release` to verify configuration
- [ ] T005 [US1] Create test release to TestPyPI to validate workflow (tag with v0.1.0-rc1)

**Checkpoint**: At this point, User Story 1 should be fully functional - wheels build on GitHub Actions and can be published to PyPI.

**Commit after phase**: `feat(009): Phase 3 - US1 PyPI packaging and release workflow`

---

## Phase 4: User Story 2 - End-to-End Tutorial (Priority: P2)

**Goal**: Provide new users with a step-by-step guide from install to first successful policy application.

**Independent Test**: A new user can follow docs/tutorial.md and successfully scan files, create a policy, and run a dry-run apply.

### Implementation for User Story 2

- [x] T006 [US2] Create end-to-end tutorial document in docs/tutorial.md
- [x] T007 [US2] Update documentation index to include tutorial in docs/INDEX.md
- [x] T008 [US2] Verify all tutorial commands execute correctly on fresh installation

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently - users can install and follow the tutorial.

**Commit after phase**: `feat(009): Phase 4 - US2 End-to-end tutorial documentation`

---

## Phase 5: User Story 3 - Plugin Author Guide (Priority: P3)

**Goal**: Enable plugin developers to create, test, and publish VPO plugins using clear documentation and a template.

**Independent Test**: A developer can copy examples/plugins/hello_world/, modify it, install with `pip install -e .`, and see the plugin in `vpo plugins list`.

### Implementation for User Story 3

- [x] T009 [P] [US3] Create hello_world plugin template directory structure in examples/plugins/hello_world/
- [x] T010 [P] [US3] Create plugin template pyproject.toml with entry point in examples/plugins/hello_world/pyproject.toml
- [x] T011 [P] [US3] Create plugin template implementation in examples/plugins/hello_world/src/hello_world/__init__.py
- [x] T012 [P] [US3] Create plugin template README in examples/plugins/hello_world/README.md
- [x] T013 [US3] Create plugin author guide document in docs/plugin-author-guide.md
- [x] T014 [US3] Update documentation index to include plugin author guide in docs/INDEX.md
- [x] T015 [US3] Verify hello_world template passes ruff check, installs correctly, and has no type errors (if type hints used)

**Checkpoint**: At this point, User Stories 1, 2, AND 3 should all work independently.

**Commit after phase**: `feat(009): Phase 5 - US3 Plugin author guide and hello_world template`

---

## Phase 6: User Story 4 - Container Image Installation (Priority: P4)

**Goal**: Provide a Docker image with VPO and all dependencies (ffmpeg, mkvtoolnix) pre-installed.

**Independent Test**: Run `docker run --rm -v ~/Videos:/data ghcr.io/randomparity/vpo:latest scan /data` and see scan results.

### Implementation for User Story 4

- [ ] T016 [P] [US4] Create VPO container directory structure in docker/vpo/
- [ ] T017 [US4] Create multi-stage Dockerfile for VPO with all dependencies in docker/vpo/Dockerfile
- [ ] T018 [US4] Create Docker workflow for building and pushing images in .github/workflows/docker.yml
- [ ] T019 [US4] Create container usage documentation in docker/vpo/README.md (include volume mount permissions guidance)
- [ ] T020 [US4] Test container build locally with `docker build -t vpo:test docker/vpo/`
- [ ] T021 [US4] Verify container size is under 500MB and includes ffmpeg, mkvtoolnix

**Checkpoint**: At this point, User Stories 1-4 should all work independently.

**Commit after phase**: `feat(009): Phase 6 - US4 Container image with all dependencies`

---

## Phase 7: User Story 5 - Backlog and Roadmap (Priority: P5)

**Goal**: Establish project direction visibility through README roadmap and organized GitHub Issues.

**Independent Test**: A contributor can view README.md Roadmap section and find issues labeled `good-first-issue`.

### Implementation for User Story 5

- [ ] T022 [P] [US5] Create GitHub issue labels (epic, good-first-issue, help-wanted, priority:*) via gh CLI
- [ ] T023 [P] [US5] Create GitHub issue templates in .github/ISSUE_TEMPLATE/
- [ ] T024 [US5] Create GitHub issues for future epics (Windows support, GPU transcoding, Web UI, etc.)
- [ ] T025 [US5] Add Roadmap section to README.md
- [ ] T026 [US5] Identify and label 2-3 existing issues as good-first-issue

**Checkpoint**: All user stories complete and independently testable.

**Commit after phase**: `feat(009): Phase 7 - US5 Roadmap and backlog organization`

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cross-story improvements

- [ ] T027 Run quickstart.md validation scenarios (all 5)
- [ ] T028 Update CONTRIBUTING.md with release process documentation
- [ ] T029 Final review of all new documentation for consistency
- [ ] T030 Create PR for feature branch with comprehensive description

**Commit after phase**: `feat(009): Phase 8 - Polish and documentation review`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No tasks - existing infrastructure
- **Foundational (Phase 2)**: No tasks - no blocking prerequisites
- **User Stories (Phase 3-7)**: All independent, can proceed in priority order
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies - can start immediately
- **User Story 2 (P2)**: No dependencies - can start immediately (in parallel with US1)
- **User Story 3 (P3)**: No dependencies - can start immediately (in parallel with US1/US2)
- **User Story 4 (P4)**: Depends on US1 (needs release workflow pattern) - but can be developed in parallel
- **User Story 5 (P5)**: No dependencies - can start immediately (in parallel with others)

### Within Each User Story

- Parallel tasks marked [P] can run simultaneously
- Sequential tasks should complete in order (especially verification tasks)
- Commit after each phase completes per user request

### Parallel Opportunities

- T001 and T002 can run in parallel (different files)
- T009, T010, T011, T012 can run in parallel (plugin template files)
- T016 and T018 can run in parallel (docker directory vs workflow)
- T022 and T023 can run in parallel (labels vs templates)

---

## Parallel Example: User Story 3 (Plugin Author Guide)

```bash
# Launch all template files in parallel:
Task: "Create hello_world plugin template directory structure in examples/plugins/hello_world/"
Task: "Create plugin template pyproject.toml with entry point in examples/plugins/hello_world/pyproject.toml"
Task: "Create plugin template implementation in examples/plugins/hello_world/src/hello_world/__init__.py"
Task: "Create plugin template README in examples/plugins/hello_world/README.md"

# Then sequentially:
Task: "Create plugin author guide document in docs/plugin-author-guide.md"
Task: "Update documentation index to include plugin author guide in docs/INDEX.md"
Task: "Verify hello_world template passes ruff check and installs correctly"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 3: User Story 1 (PyPI Packaging)
2. **STOP and VALIDATE**: Test installation from TestPyPI
3. Commit: `feat(009): Phase 3 - US1 PyPI packaging and release workflow`
4. Deploy/demo if ready

### Incremental Delivery

1. User Story 1 → Commit → Users can install via pip
2. User Story 2 → Commit → Users have tutorial guidance
3. User Story 3 → Commit → Developers can create plugins
4. User Story 4 → Commit → Users can use container
5. User Story 5 → Commit → Contributors have roadmap
6. Polish → Commit → Final PR

### Commit After Each Phase (Per User Request)

Each phase ends with a git commit:
- Phase 3: `feat(009): Phase 3 - US1 PyPI packaging and release workflow`
- Phase 4: `feat(009): Phase 4 - US2 End-to-end tutorial documentation`
- Phase 5: `feat(009): Phase 5 - US3 Plugin author guide and hello_world template`
- Phase 6: `feat(009): Phase 6 - US4 Container image with all dependencies`
- Phase 7: `feat(009): Phase 7 - US5 Roadmap and backlog organization`
- Phase 8: `feat(009): Phase 8 - Polish and documentation review`

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each phase per user request
- Stop at any checkpoint to validate story independently
- This feature is documentation/CI-focused with no new Python code in src/
