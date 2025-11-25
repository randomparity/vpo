# Tasks: Policy Validation and Error Reporting

**Input**: Design documents from `/specs/025-policy-validation/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are included per TDD approach for this feature.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `src/video_policy_orchestrator/`
- **Frontend**: `src/video_policy_orchestrator/server/static/js/`
- **Tests**: `tests/unit/`, `tests/integration/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and shared validation infrastructure

- [X] T001 Create validation module file at src/video_policy_orchestrator/policy/validation.py
- [X] T002 [P] Add ValidationError dataclass to src/video_policy_orchestrator/policy/validation.py with fields: field, message, code
- [X] T003 [P] Add ValidationResult dataclass to src/video_policy_orchestrator/policy/validation.py with fields: success, errors, policy
- [X] T004 [P] Add FieldChange dataclass to src/video_policy_orchestrator/policy/validation.py with fields: field, change_type, details
- [X] T005 Add DiffSummary dataclass to src/video_policy_orchestrator/policy/validation.py with changes list and to_summary_text() method

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core helper functions that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Add format_pydantic_errors() function in src/video_policy_orchestrator/policy/validation.py to convert Pydantic ValidationError.errors() to list of ValidationError dataclasses
- [X] T007 Add validate_policy_data() function in src/video_policy_orchestrator/policy/validation.py that uses PolicyModel and returns ValidationResult
- [X] T008 [P] Add unit tests for format_pydantic_errors() in tests/unit/policy/test_validation.py
- [X] T009 [P] Add unit tests for validate_policy_data() in tests/unit/policy/test_validation.py
- [X] T010 Export new validation classes in src/video_policy_orchestrator/policy/__init__.py

**Checkpoint**: Foundation ready - validation helpers tested and working

---

## Phase 3: User Story 1 & 2 - Save with Validation Feedback (Priority: P1) 🎯 MVP

**Goal**: Enhanced PUT /api/policies/{name} returns structured field-level errors on failure and success message with changed fields on success

**Independent Test**: Make valid changes → Save → See success with changed fields list. Make invalid changes → Save → See field-level error messages.

### Tests for User Stories 1 & 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T011 [P] [US1] Add test for successful save with changed_fields response in tests/integration/test_policy_editor_flow.py
- [X] T012 [P] [US2] Add test for validation error response with multiple field errors in tests/integration/test_policy_editor_flow.py
- [X] T013 [P] [US2] Add test for invalid language code error response in tests/integration/test_policy_editor_flow.py
- [X] T014 [P] [US2] Add test for empty required list error response in tests/integration/test_policy_editor_flow.py

### Backend Implementation for User Stories 1 & 2

- [X] T015 [US1] Modify api_policy_update_handler in src/video_policy_orchestrator/server/ui/routes.py to use validate_policy_data() before saving
- [X] T016 [US2] Modify api_policy_update_handler in src/video_policy_orchestrator/server/ui/routes.py to return structured errors array on validation failure (HTTP 400)
- [X] T017 [US1] Modify api_policy_update_handler in src/video_policy_orchestrator/server/ui/routes.py to return success response with changed_fields list (HTTP 200)
- [X] T018 [US2] Add ValidationErrorResponse model to src/video_policy_orchestrator/server/ui/models.py with error, errors, details fields
- [X] T019 [US1] Add PolicySaveSuccessResponse model to src/video_policy_orchestrator/server/ui/models.py with success, changed_fields, policy fields

### Frontend Implementation for User Stories 1 & 2

- [X] T020 [US2] Add showErrors(errors) function in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js to display multiple field-level errors
- [X] T021 [US2] Update savePolicy() in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js to handle errors array response and call showErrors()
- [X] T022 [US2] Add field-level error highlighting in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js
- [X] T022a [US2] Implement scroll-to-first-error and focus behavior in showErrors() in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js
- [X] T023 [US1] Update savePolicy() success handler in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js to display changed_fields in success message
- [X] T024 [P] [US2] Add CSS styles for field-level error display in src/video_policy_orchestrator/server/static/css/main.css

**Checkpoint**: Save with validation feedback works. Users see field-level errors or success with changed fields list.

---

## Phase 4: User Story 3 - Test Policy Without Saving (Priority: P2)

**Goal**: New POST /api/policies/{name}/validate endpoint validates without persisting; "Test Policy" button triggers it

**Independent Test**: Make changes → Click "Test Policy" → See validation result → Verify policy file unchanged on disk.

### Tests for User Story 3

- [X] T025 [P] [US3] Add test for validate endpoint returning valid=true in tests/integration/test_policy_editor_flow.py
- [X] T026 [P] [US3] Add test for validate endpoint returning errors array when invalid in tests/integration/test_policy_editor_flow.py
- [X] T027 [P] [US3] Add test verifying validate endpoint does not modify policy file in tests/integration/test_policy_editor_flow.py

### Backend Implementation for User Story 3

- [X] T028 [US3] Add api_policy_validate_handler function in src/video_policy_orchestrator/server/ui/routes.py for POST /api/policies/{name}/validate
- [X] T029 [US3] Register validate endpoint route in src/video_policy_orchestrator/server/ui/routes.py route setup
- [X] T030 [US3] Add PolicyValidateResponse model to src/video_policy_orchestrator/server/ui/models.py with valid, errors, message fields

### Frontend Implementation for User Story 3

- [X] T031 [US3] Add "Test Policy" button HTML in src/video_policy_orchestrator/server/ui/templates/policy_editor.html next to Save button
- [X] T032 [US3] Add testPolicy() function in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js calling validate endpoint
- [X] T033 [US3] Add event listener for Test Policy button in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js
- [X] T034 [US3] Handle validation response in testPolicy() to show "Policy configuration is valid" or field errors

**Checkpoint**: Test Policy button works. Users can validate without saving.

---

## Phase 5: User Story 4 - Real-time Field Validation (Priority: P2)

**Goal**: Immediate visual feedback while typing in language code and regex pattern inputs

**Dependencies**: Phase 1 only (frontend-only feature; no backend changes required)

**Independent Test**: Type invalid language code → See red border immediately. Type valid code → See green border.

### Frontend Implementation for User Story 4

- [X] T035 [P] [US4] Add validateRegexInput() function in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js for commentary pattern validation
- [X] T036 [US4] Add input event listener for commentary pattern field to call validateRegexInput() in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js
- [X] T037 [US4] Add input event listener for subtitle language field to call validateLanguageInput() in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js (already present)
- [X] T038 [P] [US4] Add CSS styles for valid/invalid input states for regex fields in src/video_policy_orchestrator/server/static/css/main.css (already present)

**Checkpoint**: Real-time validation works for all text inputs.

---

## Phase 6: User Story 5 - View Diff Summary on Successful Save (Priority: P3)

**Goal**: Success message includes human-readable summary of what fields changed and how

**Independent Test**: Reorder audio languages → Save → See "audio_language_preference: order changed" in success message.

### Tests for User Story 5

- [X] T039 [P] [US5] Add unit tests for DiffSummary.compare_policies() in tests/unit/policy/test_validation.py covering reorder, add, remove, modify cases
- [X] T040 [P] [US5] Add unit tests for DiffSummary.to_summary_text() output format in tests/unit/policy/test_validation.py

### Backend Implementation for User Story 5

- [X] T041 [US5] Add compare_policies(old_data, new_data) static method to DiffSummary class in src/video_policy_orchestrator/policy/validation.py
- [X] T042 [US5] Implement list comparison logic in compare_policies() detecting reorder, items_added, items_removed in src/video_policy_orchestrator/policy/validation.py
- [X] T043 [US5] Implement dict comparison logic in compare_policies() for default_flags changes in src/video_policy_orchestrator/policy/validation.py
- [X] T044 [US5] Modify api_policy_update_handler in src/video_policy_orchestrator/server/ui/routes.py to compute and return DiffSummary in success response

### Frontend Implementation for User Story 5

- [X] T045 [US5] Update success message display in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js to format and show diff summary from changed_fields

**Checkpoint**: Diff summary displays on successful save.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cleanup, and final validation

- [X] T046 [P] Update docs/usage/policy-editor.md with validation error handling documentation
- [X] T047 [P] Add edge case handling for unexpected error formats in savePolicy() and testPolicy() in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js
- [X] T048 [P] Add network error handling with user-friendly messages in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js
- [X] T049 Run quickstart.md validation scenarios manually
- [X] T050 Run full test suite: uv run pytest tests/unit/policy/test_validation.py tests/integration/test_policy_editor_flow.py -v

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories 1 & 2 (Phase 3)**: Depends on Foundational - MVP
- **User Story 3 (Phase 4)**: Depends on Foundational - Can parallel with Phase 3
- **User Story 4 (Phase 5)**: No backend dependencies - Can parallel with Phase 3/4
- **User Story 5 (Phase 6)**: Depends on Phase 3 (uses same success response)
- **Polish (Phase 7)**: Depends on all user stories complete

### User Story Dependencies

- **User Story 1 & 2 (P1)**: Can start after Foundational (Phase 2) - These are tightly coupled (same endpoint)
- **User Story 3 (P2)**: Can start after Foundational - Independent new endpoint
- **User Story 4 (P2)**: Can start after Phase 1 Setup - Frontend only, no Phase 2 dependency
- **User Story 5 (P3)**: Depends on US1/US2 completion - Extends success response

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Backend changes before frontend changes (API contract first)
- Models/dataclasses before handlers
- Story complete before moving to next priority

### Parallel Opportunities

- T002, T003, T004 can run in parallel (different dataclasses in same file)
- T008, T009 can run in parallel (different test functions)
- T011, T012, T013, T014 can run in parallel (different test cases)
- T025, T026, T027 can run in parallel (different test cases)
- T035, T038 can run in parallel (JS function and CSS)
- T039, T040 can run in parallel (different test functions)
- T046, T047, T048 can run in parallel (different files)

---

## Parallel Example: Phase 3 (MVP)

```bash
# Launch all tests for User Stories 1 & 2 together:
Task T011: "test for successful save with changed_fields response"
Task T012: "test for validation error response with multiple field errors"
Task T013: "test for invalid language code error response"
Task T014: "test for empty required list error response"

# After tests fail, implement backend in sequence:
Task T015 → T016 → T017 (same file, logical order)
Task T018, T019 in parallel (different models)

# Then implement frontend:
Task T020 → T021 → T022 → T023 (same file, depends on each other)
Task T024 in parallel (different file - CSS)
```

---

## Implementation Strategy

### MVP First (User Stories 1 & 2 Only)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006-T010)
3. Complete Phase 3: User Stories 1 & 2 (T011-T024)
4. **STOP and VALIDATE**: Test save with valid and invalid data
5. Deploy/demo if ready - Basic validation feedback working

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Stories 1 & 2 → Test → Deploy (MVP!)
3. Add User Story 3 (Test Policy) → Test → Deploy
4. Add User Story 4 (Real-time) → Test → Deploy
5. Add User Story 5 (Diff Summary) → Test → Deploy
6. Polish phase → Final release

### Parallel Team Strategy

With multiple developers after Foundational is complete:

- Developer A: User Stories 1 & 2 (backend)
- Developer B: User Stories 1 & 2 (frontend)
- Developer C: User Story 4 (frontend only - can start immediately)

---

## Notes

- [P] tasks = different files or independent test cases
- [Story] label maps task to specific user story for traceability
- US1 and US2 share the same phase because they modify the same endpoint
- US4 (real-time validation) has no backend dependencies - can start early
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
