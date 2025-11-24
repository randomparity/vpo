# Tasks: Transcription Detail View

**Input**: Design documents from `/specs/022-transcription-detail/`
**Prerequisites**: plan.md, spec.md, data-model.md, research.md, quickstart.md

**Tests**: Not explicitly requested in specification - test tasks included as optional.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths included in all descriptions

## Path Conventions

This feature follows the existing VPO structure:
- **Source**: `src/video_policy_orchestrator/`
- **Tests**: `tests/unit/`, `tests/integration/`
- **Templates**: `src/video_policy_orchestrator/server/ui/templates/sections/`

---

## Phase 1: Setup

**Purpose**: No new project setup required - this feature extends existing infrastructure

*This feature uses existing project structure. No setup tasks needed.*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data layer that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T001 Add `get_transcription_detail()` query function in `src/video_policy_orchestrator/db/models.py`
- [ ] T002 [P] Add `get_classification_reasoning()` helper function in `src/video_policy_orchestrator/server/ui/models.py`
- [ ] T003 [P] Add `highlight_keywords_in_transcript()` helper function in `src/video_policy_orchestrator/server/ui/models.py`
- [ ] T004 [P] Add `TRANSCRIPT_DISPLAY_LIMIT` constant (10000) in `src/video_policy_orchestrator/server/ui/models.py`

**Checkpoint**: Foundation ready - all helper functions and DB query available for user stories

---

## Phase 3: User Story 1 - View Transcription Detail (Priority: P1) MVP

**Goal**: Display complete transcription information for a single audio track including language detection, confidence, and transcript text

**Independent Test**: Navigate to `/transcriptions/{id}` and verify all fields display correctly (track metadata, detected language, confidence score, transcript text)

### Implementation for User Story 1

- [ ] T005 [P] [US1] Add `TranscriptionDetailItem` dataclass in `src/video_policy_orchestrator/server/ui/models.py`
- [ ] T006 [P] [US1] Add `TranscriptionDetailResponse` dataclass in `src/video_policy_orchestrator/server/ui/models.py`
- [ ] T007 [P] [US1] Add `TranscriptionDetailContext` dataclass with `from_transcription_and_request()` in `src/video_policy_orchestrator/server/ui/models.py`
- [ ] T008 [US1] Add `_build_transcription_detail_item()` builder function in `src/video_policy_orchestrator/server/ui/routes.py`
- [ ] T009 [US1] Add `transcription_detail_handler()` HTML route handler in `src/video_policy_orchestrator/server/ui/routes.py`
- [ ] T010 [US1] Add `api_transcription_detail_handler()` JSON API handler in `src/video_policy_orchestrator/server/ui/routes.py`
- [ ] T011 [US1] Register routes `/transcriptions/{transcription_id}` and `/api/transcriptions/{transcription_id}` in `setup_ui_routes()` in `src/video_policy_orchestrator/server/ui/routes.py`
- [ ] T012 [US1] Create `transcription_detail.html` template in `src/video_policy_orchestrator/server/ui/templates/sections/transcription_detail.html`
- [ ] T013 [US1] Add 404 error handling for invalid transcription IDs in handlers
- [ ] T014 [US1] Add 400 error handling for malformed transcription IDs in handlers
- [ ] T015 [US1] Add low-confidence warning indicator CSS (`.confidence-low` with warning styling) in `src/video_policy_orchestrator/server/static/css/main.css`

**Checkpoint**: User Story 1 complete - basic detail page displays all transcription data with navigation and low-confidence indicators

---

## Phase 4: User Story 2 - Read Long Transcription Content (Priority: P2)

**Goal**: Handle long transcription text (> 500 chars) with proper formatting and truncation indicators

**Independent Test**: View a transcription with > 500 characters and verify text is readable, properly wrapped, with truncation indicator if > 10,000 chars

### Implementation for User Story 2

- [ ] T016 [US2] Add CSS styles for transcript text display in `src/video_policy_orchestrator/server/static/css/main.css`
- [ ] T017 [US2] Add `.transcript-content` class with `word-break: break-word` and `overflow-wrap: break-word` in `src/video_policy_orchestrator/server/static/css/main.css`
- [ ] T018 [US2] Add `.truncation-notice` class for truncation indicator styling in `src/video_policy_orchestrator/server/static/css/main.css`
- [ ] T019 [US2] Update template to show truncation notice when `transcript_truncated` is true in `src/video_policy_orchestrator/server/ui/templates/sections/transcription_detail.html`
- [ ] T020 [US2] Add empty state message "No transcription text available" in template for null transcript in `src/video_policy_orchestrator/server/ui/templates/sections/transcription_detail.html`

**Checkpoint**: User Story 2 complete - long text displays properly with truncation handling

---

## Phase 5: User Story 3 - Understand Commentary Detection (Priority: P3)

**Goal**: Show commentary classification reasoning with matched keywords/patterns highlighted

**Independent Test**: View a commentary-classified track and verify classification source is shown, keywords are highlighted in transcript

### Implementation for User Story 3

- [ ] T021 [US3] Add `.commentary-match` CSS class for highlighted keywords in `src/video_policy_orchestrator/server/static/css/main.css`
- [ ] T022 [US3] Add commentary reasoning section to template showing `classification_source` and `matched_keywords` in `src/video_policy_orchestrator/server/ui/templates/sections/transcription_detail.html`
- [ ] T023 [US3] Add conditional display for commentary badge in template header in `src/video_policy_orchestrator/server/ui/templates/sections/transcription_detail.html`
- [ ] T024 [US3] Display `transcript_html` with `| safe` filter to render highlighted keywords in `src/video_policy_orchestrator/server/ui/templates/sections/transcription_detail.html`

**Checkpoint**: User Story 3 complete - commentary detection reasoning and highlighting visible

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Integration with existing views and final polish

- [ ] T025 [P] Add link from File Detail audio track transcription info to `/transcriptions/{id}` in `src/video_policy_orchestrator/server/ui/templates/sections/file_detail.html`
- [ ] T026 [P] Add link from Transcriptions List to individual transcription detail pages in `src/video_policy_orchestrator/server/ui/templates/sections/transcriptions.html`
- [ ] T027 Update imports in `src/video_policy_orchestrator/server/ui/models.py` exports if needed
- [ ] T028 Run linting and formatting (`uv run ruff check . && uv run ruff format .`)
- [ ] T029 Validate feature against quickstart.md test scenarios

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Skipped - using existing infrastructure
- **Foundational (Phase 2)**: No dependencies - can start immediately
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - User stories can proceed in priority order (P1 → P2 → P3)
  - US2 and US3 enhance US1 but don't require US1 code changes
- **Polish (Phase 6)**: Depends on User Story 1 being complete (needs routes registered)

### User Story Dependencies

- **User Story 1 (P1)**: Depends only on Foundational (T001-T004)
- **User Story 2 (P2)**: Depends on US1 (template and models must exist)
- **User Story 3 (P3)**: Depends on US1 (template must exist); uses T002, T003 helpers

**Note**: T015 (low-confidence indicator) moved to US1 per SC-003 requirement.

### Within Each User Story

- Models/dataclasses before handlers
- Handlers before template
- Core implementation before error handling
- Template structure before styling

### Parallel Opportunities

- T002, T003, T004 can run in parallel (different functions, same file - edit sequentially)
- T005, T006, T007 can run in parallel (different dataclasses)
- T025, T026 can run in parallel (different files)

---

## Parallel Example: Foundational Phase

```bash
# These can be developed in parallel (different responsibilities):
T001: DB query function (db/models.py)
T002: Classification reasoning helper (ui/models.py)
T003: Highlight helper (ui/models.py)
```

## Parallel Example: User Story 1 Models

```bash
# Launch all dataclass definitions together:
T005: TranscriptionDetailItem dataclass
T006: TranscriptionDetailResponse dataclass
T007: TranscriptionDetailContext dataclass
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (T001-T004)
2. Complete Phase 3: User Story 1 (T005-T015)
3. **STOP and VALIDATE**: Test `/transcriptions/{id}` displays all data with low-confidence indicators
4. Ship MVP - basic detail view is functional

### Incremental Delivery

1. Foundational → Foundation ready
2. User Story 1 → Test independently → Deploy (MVP!)
3. User Story 2 → Test long text handling → Deploy
4. User Story 3 → Test commentary highlighting → Deploy
5. Polish → Integration with existing views

### Recommended Execution Order

```
T001 → T002 → T003 → T004 (Foundational)
    ↓
T005 → T006 → T007 (Models - can parallel)
    ↓
T008 → T009 → T010 → T011 (Handlers + Routes)
    ↓
T012 → T013 → T014 → T015 (Template + Error handling + Low-confidence CSS)
    ↓
T016 → T017 → T018 → T019 → T020 (US2 - Long text)
    ↓
T021 → T022 → T023 → T024 (US3 - Commentary)
    ↓
T025 → T026 → T027 → T028 → T029 (Polish)
```

---

## Notes

- All file paths are absolute from repository root
- Existing patterns from `job_detail_handler` and `file_detail_handler` should be followed
- Template extends `base.html` and follows existing section template patterns
- No schema changes required - uses existing `transcription_results` table
- Commentary keywords defined in `transcription/models.py` - import and reuse
