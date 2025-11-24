# Implementation Tasks: Visual Policy Editor

**Feature**: 024-policy-editor
**Branch**: `024-policy-editor`
**Generated**: 2025-11-24

This document provides a dependency-ordered, user-story-based task breakdown for implementing the Visual Policy Editor feature.

---

## Implementation Strategy

**MVP Scope**: User Stories 1, 2, 6, 7 (Edit Track Ordering, Audio Preferences, Save Changes, Preserve Unknown Fields)

**Incremental Delivery**: Each user story phase is independently testable and delivers value. Phases can be implemented and merged sequentially, enabling early feedback and iterative refinement.

**Parallelization**: Tasks marked with `[P]` can be executed in parallel when working with multiple developers or AI agents.

---

## Dependencies

### User Story Completion Order

```
Phase 1 (Setup) → Phase 2 (Foundation)
                    ↓
    ┌───────────────┼───────────────┐
    ↓               ↓               ↓
Phase 3 (US1)   Phase 3 (US2)   Phase 3 (US6+US7)
    ↓               ↓               ↓
Phase 4 (US3)   Phase 4 (US4)   Phase 4 (US5)
    └───────────────┼───────────────┘
                    ↓
            Phase 5 (Polish)
```

**Key Dependencies**:
- Phase 2 (Foundation) blocks all user story phases
- US1, US2, US6+US7 are independent (can implement in parallel)
- US3, US4, US5 are enhancements (implement after MVP)

**Independent User Stories** (no cross-dependencies):
- US1: Edit Track Ordering (P1)
- US2: Configure Audio Preferences (P1)
- US3: Configure Subtitle Defaults (P2)
- US4: Configure Commentary Detection (P2)
- US5: View Raw Policy Representation (P2)
- US6: Save Policy Changes (P1) - depends on US1, US2 for testing
- US7: Preserve Unknown Fields (P1) - architectural requirement

---

## Phase 1: Setup & Prerequisites

**Goal**: Install dependencies and set up development environment

**Independent Test**: Dependencies installed, ruamel.yaml available, server starts successfully

### Tasks

- [ ] T001 Add ruamel.yaml dependency to pyproject.toml
- [ ] T002 Install dependencies via `uv pip install -e ".[dev]"`
- [ ] T003 Verify ruamel.yaml import works in Python REPL
- [ ] T004 Create test policy fixtures directory at tests/fixtures/policies/

**Commit Point**: `git commit -m "chore: Add ruamel.yaml dependency and test fixtures directory"`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Goal**: Implement core policy round-trip logic that ALL user stories depend on

**Independent Test**: Can load policy with unknown fields, modify one field, save, and verify unknown fields preserved

**CRITICAL**: No user story work can begin until this phase is complete

### Tasks

- [ ] T005 Create PolicyRoundTripEditor class in src/video_policy_orchestrator/policy/editor.py
- [ ] T006 Implement load() method using ruamel.yaml with round-trip mode in src/video_policy_orchestrator/policy/editor.py
- [ ] T007 Implement save() method with selective field updates in src/video_policy_orchestrator/policy/editor.py
- [ ] T008 Add structured logging for policy edits (policy name, fields changed) in src/video_policy_orchestrator/policy/editor.py
- [ ] T009 Create unit tests for unknown field preservation in tests/unit/policy/test_policy_roundtrip.py
- [ ] T010 Create unit tests for comment preservation (best-effort) in tests/unit/policy/test_policy_roundtrip.py
- [ ] T011 Add PolicyEditorContext dataclass in src/video_policy_orchestrator/server/ui/models.py
- [ ] T012 Add PolicyEditorRequest dataclass in src/video_policy_orchestrator/server/ui/models.py

**Commit Point**: `git commit -m "feat: Implement policy round-trip editor with field preservation"`

---

## Phase 3: Core Editing Features (MVP)

### User Story 1: Edit Track Ordering Rules (P1)

**Goal**: Users can reorder track types via form controls

**Independent Test**: Open policy editor, reorder track types using up/down buttons, save, verify YAML file reflects new order

#### Tasks

- [ ] T013 [P] [US1] Add GET /policies/{name}/edit route in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T014 [P] [US1] Create policy_editor.html template in src/video_policy_orchestrator/server/ui/templates/policy_editor.html
- [ ] T015 [P] [US1] Add track ordering section HTML with reorderable list in src/video_policy_orchestrator/server/ui/templates/policy_editor.html
- [ ] T016 [US1] Create state-manager.js with Proxy-based reactivity in src/video_policy_orchestrator/server/static/js/policy-editor/state-manager.js
- [ ] T017 [US1] Implement track ordering UI controls (up/down buttons) in src/video_policy_orchestrator/server/static/js/policy-editor/track-ordering.js
- [ ] T018 [US1] Wire track ordering to form state in src/video_policy_orchestrator/server/static/js/policy-editor/form-bindings.js
- [ ] T019 [US1] Add track_order validation (non-empty, valid types) in src/video_policy_orchestrator/server/static/js/policy-editor/validators.js

**Commit Point**: `git commit -m "feat(US1): Implement track ordering editor with reorderable list controls"`

---

### User Story 2: Configure Audio Preferences (P1)

**Goal**: Users can manage audio language preferences via ordered list with autocomplete

**Independent Test**: Open policy editor, add/remove/reorder audio languages, save, verify YAML reflects changes

#### Tasks

- [ ] T020 [P] [US2] Add audio preferences section HTML in src/video_policy_orchestrator/server/ui/templates/policy_editor.html
- [ ] T021 [P] [US2] Create language-autocomplete.js component in src/video_policy_orchestrator/server/static/js/policy-editor/language-autocomplete.js
- [ ] T022 [P] [US2] Load ISO 639-2 language list data in src/video_policy_orchestrator/server/static/data/iso-639-2.json
- [ ] T023 [US2] Implement accessible autocomplete with ARIA roles in src/video_policy_orchestrator/server/static/js/policy-editor/language-autocomplete.js
- [ ] T024 [US2] Add audio language list with button-based reordering in src/video_policy_orchestrator/server/static/js/policy-editor/language-list.js
- [ ] T025 [US2] Wire audio preferences to form state in src/video_policy_orchestrator/server/static/js/policy-editor/form-bindings.js
- [ ] T026 [US2] Add audio_language_preference validation (non-empty, ISO 639-2 codes) in src/video_policy_orchestrator/server/static/js/policy-editor/validators.js

**Commit Point**: `git commit -m "feat(US2): Implement audio preferences editor with accessible autocomplete"`

---

### User Story 6 + 7: Save Changes & Preserve Unknown Fields (P1)

**Goal**: Users can save policy changes with clear feedback, unknown fields are preserved

**Independent Test**: Make changes to policy, save, verify success message appears, file updated, unknown fields preserved

#### Tasks

- [ ] T027 [P] [US6] Add GET /api/policies/{name} endpoint in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T028 [P] [US6] Add PUT /api/policies/{name} endpoint in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T029 [P] [US6] Add GET /api/policies/schema endpoint for JSON Schema in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T030 [US6] Implement save button handler with validation in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js
- [ ] T031 [US6] Add success/error feedback UI in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js
- [ ] T032 [US6] Implement unsaved changes warning (beforeunload) in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js
- [ ] T033 [US6] Add client-side validation using Ajv for JSON Schema in src/video_policy_orchestrator/server/static/js/policy-editor/validators.js
- [ ] T034 [P] [US7] Add integration test for unknown field preservation in tests/integration/test_policy_editor_flow.py
- [ ] T035 [P] [US7] Add integration test for comment preservation in tests/integration/test_policy_editor_flow.py
- [ ] T036 [US6] Handle concurrent modification detection (409 errors) in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js

**Commit Point**: `git commit -m "feat(US6+US7): Implement save functionality with field preservation and validation"`

---

## Phase 4: Enhanced Features

### User Story 3: Configure Subtitle Defaults (P2)

**Goal**: Users can manage subtitle language preferences and default flags

**Independent Test**: Open policy editor, configure subtitle preferences, toggle default flags, save, verify YAML updated

#### Tasks

- [ ] T037 [P] [US3] Add subtitle preferences section HTML in src/video_policy_orchestrator/server/ui/templates/policy_editor.html
- [ ] T038 [P] [US3] Add default flags section HTML with checkboxes in src/video_policy_orchestrator/server/ui/templates/policy_editor.html
- [ ] T039 [US3] Wire subtitle language list to form state (reuse language-list.js) in src/video_policy_orchestrator/server/static/js/policy-editor/form-bindings.js
- [ ] T040 [US3] Wire default flags checkboxes to form state in src/video_policy_orchestrator/server/static/js/policy-editor/form-bindings.js
- [ ] T041 [US3] Add subtitle_language_preference validation in src/video_policy_orchestrator/server/static/js/policy-editor/validators.js

**Commit Point**: `git commit -m "feat(US3): Implement subtitle preferences and default flags editor"`

---

### User Story 4: Configure Commentary Detection (P2)

**Goal**: Users can manage commentary patterns and detection settings

**Independent Test**: Open policy editor, add/remove commentary patterns, toggle detection options, save, verify YAML updated

#### Tasks

- [ ] T042 [P] [US4] Add commentary section HTML in src/video_policy_orchestrator/server/ui/templates/policy_editor.html
- [ ] T043 [US4] Implement commentary patterns list with add/remove in src/video_policy_orchestrator/server/static/js/policy-editor/commentary-patterns.js
- [ ] T044 [US4] Wire commentary patterns to form state in src/video_policy_orchestrator/server/static/js/policy-editor/form-bindings.js
- [ ] T045 [US4] Add commentary_patterns validation (valid regex) in src/video_policy_orchestrator/server/static/js/policy-editor/validators.js
- [ ] T046 [US4] Add transcription settings toggles (detect_commentary, reorder_commentary) in src/video_policy_orchestrator/server/ui/templates/policy_editor.html
- [ ] T047 [US4] Add cross-field validation (reorder_commentary requires detect_commentary) in src/video_policy_orchestrator/server/static/js/policy-editor/validators.js

**Commit Point**: `git commit -m "feat(US4): Implement commentary detection configuration editor"`

---

### User Story 5: View Raw Policy Representation (P2)

**Goal**: Users see real-time YAML preview as they edit the form

**Independent Test**: Make changes in form, verify YAML preview panel updates in real-time (300ms debounce)

#### Tasks

- [ ] T048 [P] [US5] Add YAML preview panel HTML (read-only textarea) in src/video_policy_orchestrator/server/ui/templates/policy_editor.html
- [ ] T049 [US5] Create yaml-preview.js with YAML generation from state in src/video_policy_orchestrator/server/static/js/policy-editor/yaml-preview.js
- [ ] T050 [US5] Wire form state changes to YAML preview with 300ms debounce in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js
- [ ] T051 [US5] Add syntax highlighting for YAML preview (optional) in src/video_policy_orchestrator/server/static/js/policy-editor/yaml-preview.js

**Commit Point**: `git commit -m "feat(US5): Add real-time YAML preview panel"`

---

## Phase 5: Polish & Cross-Cutting Concerns

**Goal**: Complete UI polish, error handling, accessibility, and documentation

**Independent Test**: All user stories work together seamlessly, UI is accessible, documentation complete

### Tasks

- [ ] T052 [P] Create policy-editor.css with responsive layout in src/video_policy_orchestrator/server/static/css/policy-editor.css
- [ ] T053 [P] Add dark mode support to policy-editor.css in src/video_policy_orchestrator/server/static/css/policy-editor.css
- [ ] T054 [P] Add high contrast mode support in src/video_policy_orchestrator/server/static/css/policy-editor.css
- [ ] T055 Add ARIA live regions for screen reader announcements in src/video_policy_orchestrator/server/ui/templates/policy_editor.html
- [ ] T056 Add keyboard navigation support (Tab, Enter, Escape) in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js
- [ ] T057 Add loading states and spinners for async operations in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js
- [ ] T058 Add "Edit" link from policies list view in src/video_policy_orchestrator/server/ui/templates/policies.html
- [ ] T059 Handle 404 errors (policy not found) gracefully in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js
- [ ] T060 Handle 500 errors (server error) gracefully in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js
- [ ] T061 [P] Add unit tests for API routes in tests/unit/server/test_policy_editor_routes.py
- [ ] T062 [P] Add unit tests for PolicyRoundTripEditor in tests/unit/policy/test_policy_editor.py
- [ ] T063 Add E2E integration test covering full edit flow in tests/integration/test_policy_editor_flow.py
- [ ] T064 Update docs with policy editor usage guide in docs/usage/policy-editor.md
- [ ] T065 Update CLAUDE.md with policy editor development notes

**Commit Point**: `git commit -m "polish: Complete UI polish, accessibility, error handling, and documentation"`

---

## Parallel Execution Examples

### Phase 2 (Foundation) - 2 Parallel Tracks

**Track A (Backend)**:
- T005-T008: PolicyRoundTripEditor implementation

**Track B (Models)**:
- T011-T012: Data models for API

### Phase 3 (MVP) - 3 Parallel Tracks

**Track A (US1 - Track Ordering)**:
- T013-T019: Track ordering editor

**Track B (US2 - Audio Preferences)**:
- T020-T026: Audio preferences editor

**Track C (US6+US7 - Save & Preserve)**:
- T027-T036: Save API and validation

### Phase 5 (Polish) - 3 Parallel Tracks

**Track A (CSS)**:
- T052-T054: Styling and responsive design

**Track B (Tests)**:
- T061-T063: Unit and integration tests

**Track C (Docs)**:
- T064-T065: Documentation updates

---

## Task Summary

**Total Tasks**: 65
**Setup Phase**: 4 tasks
**Foundation Phase**: 8 tasks
**MVP User Stories (US1, US2, US6+US7)**: 24 tasks
**Enhancement Stories (US3, US4, US5)**: 15 tasks
**Polish Phase**: 14 tasks

**Parallelizable Tasks**: 32 (marked with [P])
**Sequential Tasks**: 33

**User Story Task Breakdown**:
- US1 (Edit Track Ordering): 7 tasks
- US2 (Audio Preferences): 7 tasks
- US3 (Subtitle Defaults): 5 tasks
- US4 (Commentary Detection): 6 tasks
- US5 (YAML Preview): 4 tasks
- US6 (Save Changes): 10 tasks
- US7 (Preserve Unknown Fields): 2 tasks (integrated with US6)

---

## Suggested MVP Scope

**Minimal Viable Product** (First Release):
1. ✅ Phase 1: Setup & Prerequisites (4 tasks)
2. ✅ Phase 2: Foundation (8 tasks)
3. ✅ US1: Edit Track Ordering (7 tasks)
4. ✅ US2: Configure Audio Preferences (7 tasks)
5. ✅ US6+US7: Save & Preserve (10 tasks)

**Total MVP**: 36 tasks

This MVP delivers:
- Core editing for track order and audio preferences (highest priority user stories)
- Save functionality with validation
- Unknown field preservation (critical for data integrity)
- Basic UI and error handling

**Post-MVP Iterations**:
- Iteration 2: Add US3 (Subtitle Defaults) + US5 (YAML Preview)
- Iteration 3: Add US4 (Commentary Detection)
- Iteration 4: Polish phase (accessibility, docs, comprehensive testing)

---

## Validation Checklist

- [x] All tasks follow checklist format: `- [ ] T### [P?] [Story?] Description with file path`
- [x] Each user story has clear independent test criteria
- [x] Task IDs are sequential (T001-T065)
- [x] Story labels match spec.md user stories (US1-US7)
- [x] Parallelizable tasks marked with [P]
- [x] Dependencies clearly documented
- [x] Commit points after each major phase
- [x] MVP scope clearly identified
- [x] File paths specified for all implementation tasks

---

## Notes

**Commit Strategy**: Regular commits after each phase ensure manageable code review per commit. Each commit represents a cohesive unit of functionality.

**Independent Testing**: Each user story phase includes its independent test criteria, ensuring features can be validated in isolation before integration.

**Technology Decisions**: All technical approaches (ruamel.yaml, Proxy-based state, hybrid validation, accessible autocomplete) have been researched and documented in research.md.

**Accessibility**: Tasks include WCAG 2.1 AA compliance (ARIA roles, keyboard navigation, screen reader support, high contrast mode).

---

**Ready to Implement**: All design artifacts complete, dependencies identified, tasks ordered by priority and dependency.
