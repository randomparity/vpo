# Tasks: File Detail View

**Input**: Design documents from `/specs/020-file-detail-view/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not explicitly requested - tests are omitted from task list.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md structure:
- **Source**: `src/vpo/`
- **Tests**: `tests/`
- **Templates**: `src/vpo/server/ui/templates/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new infrastructure needed - this feature integrates into existing web server

*No setup tasks required - using existing project structure, dependencies, and configuration.*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data access and models that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T001 Add `get_file_by_id()` function in src/vpo/db/models.py
- [X] T002 Add `get_transcriptions_for_tracks()` function in src/vpo/db/models.py
- [X] T003 [P] Add `TrackDetailItem` dataclass in src/vpo/server/ui/models.py
- [X] T004 [P] Add `TrackTranscriptionInfo` dataclass in src/vpo/server/ui/models.py
- [X] T005 [P] Add `FileDetailItem` dataclass in src/vpo/server/ui/models.py
- [X] T006 [P] Add `FileDetailResponse` dataclass in src/vpo/server/ui/models.py
- [X] T007 [P] Add `FileDetailContext` dataclass in src/vpo/server/ui/models.py
- [X] T008 [P] Add `format_file_size()` helper function in src/vpo/server/ui/models.py
- [X] T009 Add `group_tracks_by_type()` helper function in src/vpo/server/ui/models.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - View File Details from Library (Priority: P1)

**Goal**: Enable users to click a file in the Library list and navigate to a detail page showing file metadata

**Independent Test**: Scan a directory, navigate to Library, click a file row, verify navigation to `/library/{id}` with back button working

### Implementation for User Story 1

- [X] T010 [US1] Create `file_detail.html` template in src/vpo/server/ui/templates/sections/file_detail.html
- [X] T011 [US1] Implement `file_detail_handler()` HTML route handler in src/vpo/server/ui/routes.py
- [X] T012 [US1] Implement `api_file_detail_handler()` JSON API handler in src/vpo/server/ui/routes.py
- [X] T013 [US1] Register `/library/{file_id}` and `/api/library/{file_id}` routes in `setup_ui_routes()` in src/vpo/server/ui/routes.py
- [X] T014 [US1] Update library.html template to make file rows clickable in src/vpo/server/ui/templates/sections/library.html
- [X] T015 [US1] Add JavaScript row click handler in src/vpo/server/static/js/library.js

**Checkpoint**: User Story 1 complete - can navigate from Library to file detail and back

---

## Phase 4: User Story 2 - Inspect Track-Level Metadata (Priority: P1)

**Goal**: Display all tracks grouped by type (video/audio/subtitle) with relevant metadata for each track type

**Independent Test**: View a file with multiple tracks, verify tracks are grouped by type with codec, language, resolution, channels, and flags displayed

### Implementation for User Story 2

- [X] T016 [US2] Add video track section to file_detail.html template showing codec, resolution, frame rate in src/vpo/server/ui/templates/sections/file_detail.html
- [X] T017 [US2] Add audio track section to file_detail.html template showing codec, language, channels, channel_layout, title, flags in src/vpo/server/ui/templates/sections/file_detail.html
- [X] T018 [US2] Add subtitle track section to file_detail.html template showing codec, language, title, flags in src/vpo/server/ui/templates/sections/file_detail.html
- [X] T019 [US2] Add collapsible section CSS and JavaScript (threshold: 5+ total tracks per FR-013) in src/vpo/server/static/css/styles.css and src/vpo/server/static/js/file-detail.js
- [X] T020 [US2] Add flag badges (default, forced) styling in src/vpo/server/static/css/styles.css

**Checkpoint**: User Story 2 complete - track metadata fully displayed with collapsible sections

---

## Phase 5: User Story 3 - View File Information (Priority: P2)

**Goal**: Display file metadata including path, container format, size (human-readable), and dates

**Independent Test**: View any file, verify path, container format, size (e.g., "4.2 GB"), modified date, and scanned date are displayed

### Implementation for User Story 3

- [X] T021 [US3] Add file information section to file_detail.html showing path, filename, container format, size_human, modified_at, scanned_at in src/vpo/server/ui/templates/sections/file_detail.html
- [X] T022 [US3] Add scan error display when scan_status is "error" in src/vpo/server/ui/templates/sections/file_detail.html

**Checkpoint**: User Story 3 complete - file metadata fully displayed

---

## Phase 6: User Story 4 - Navigate to Related Jobs (Priority: P2)

**Goal**: Show links to scan job and policy application jobs related to the file

**Independent Test**: View a file, click scan job link, verify navigation to correct job detail page

### Implementation for User Story 4

- [X] T023 [US4] Add scan job link section to file_detail.html with link to /jobs/{scan_job_id} in src/vpo/server/ui/templates/sections/file_detail.html
- [X] T024 [US4] Handle graceful empty state when no job_id exists in src/vpo/server/ui/templates/sections/file_detail.html

**Checkpoint**: User Story 4 complete - job links functional

---

## Phase 7: User Story 5 - View Transcription Summary (Priority: P3)

**Goal**: Display transcription results (detected language, confidence) for audio tracks when available

**Independent Test**: View a file with transcription results, verify detected language and confidence percentage are shown per audio track

### Implementation for User Story 5

- [X] T025 [US5] Add transcription info display to audio track items in file_detail.html showing detected_language, confidence (as percentage), track_type in src/vpo/server/ui/templates/sections/file_detail.html
- [X] T026 [US5] Handle empty state when no transcription data exists (hide or show "No transcription data") in src/vpo/server/ui/templates/sections/file_detail.html

**Checkpoint**: User Story 5 complete - transcription data displayed

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Error handling, edge cases, and refinements

- [X] T027 [P] Add 404 error handling for non-existent file IDs in src/vpo/server/ui/routes.py
- [X] T028 [P] Add 400 error handling for invalid file ID format in src/vpo/server/ui/routes.py
- [X] T029 [P] Add 503 error handling for database unavailability in src/vpo/server/ui/routes.py
- [ ] T030 Run quickstart.md manual verification steps
- [X] T031 Run linting and formatting (uv run ruff check . && uv run ruff format .)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Not needed - using existing infrastructure
- **Foundational (Phase 2)**: BLOCKS all user stories - must complete first
- **User Stories (Phases 3-7)**: All depend on Foundational phase completion
  - US1 and US2 are both P1 priority but have implementation dependency
  - US3 and US4 are P2 priority, can proceed in parallel after US1
  - US5 is P3 priority, can proceed after Foundational
- **Polish (Phase 8)**: Can run in parallel with later user stories

### User Story Dependencies

- **User Story 1 (P1)**: Requires Foundational - Creates base route and template
- **User Story 2 (P1)**: Requires US1 template to exist - Adds track sections to it
- **User Story 3 (P2)**: Requires US1 template to exist - Adds file info section
- **User Story 4 (P2)**: Requires US1 template to exist - Adds job links section
- **User Story 5 (P3)**: Requires US2 audio track section - Adds transcription to it

### Within Each User Story

- Template structure before content sections
- Handler logic before template rendering
- Core implementation before styling/polish

### Parallel Opportunities

**Phase 2 (Foundational)**:
- T003, T004, T005, T006, T007, T008 can all run in parallel (different dataclasses)
- T001 and T002 are sequential (same file, related functions)
- T009 depends on T003 (uses TrackDetailItem)

**Phase 8 (Polish)**:
- T027, T028, T029 can all run in parallel (different error types)

---

## Parallel Example: Foundational Phase

```bash
# Launch all model dataclasses together:
Task: "Add TrackDetailItem dataclass in src/vpo/server/ui/models.py"
Task: "Add TrackTranscriptionInfo dataclass in src/vpo/server/ui/models.py"
Task: "Add FileDetailItem dataclass in src/vpo/server/ui/models.py"
Task: "Add FileDetailResponse dataclass in src/vpo/server/ui/models.py"
Task: "Add FileDetailContext dataclass in src/vpo/server/ui/models.py"
Task: "Add format_file_size() helper function in src/vpo/server/ui/models.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 2: Foundational (database + models)
2. Complete Phase 3: User Story 1 (navigation + basic page)
3. Complete Phase 4: User Story 2 (track metadata display)
4. **STOP and VALIDATE**: Test file detail view with tracks
5. Deploy/demo core functionality

### Incremental Delivery

1. Foundational → All models and DB queries ready
2. US1 → Navigation works → Can click files in Library
3. US2 → Track display works → Core value delivered (MVP!)
4. US3 → File info added → Enhanced context
5. US4 → Job links added → History navigation
6. US5 → Transcription added → Full feature complete

### Single Developer Strategy

Execute in order:
1. Phase 2: T001 → T002 → T003-T008 (parallel) → T009
2. Phase 3: T010 → T011 → T012 → T013 → T014 → T015
3. Phase 4: T016 → T017 → T018 → T019 → T020
4. Phase 5: T021 → T022
5. Phase 6: T023 → T024
6. Phase 7: T025 → T026
7. Phase 8: T027-T029 (parallel) → T030 → T031

---

## Notes

- Total tasks: 31
- User Story 1 (P1): 6 tasks (navigation + base template)
- User Story 2 (P1): 5 tasks (track display)
- User Story 3 (P2): 2 tasks (file info)
- User Story 4 (P2): 2 tasks (job links)
- User Story 5 (P3): 2 tasks (transcription)
- Foundational: 9 tasks (models + DB)
- Polish: 5 tasks (error handling + validation)
- Parallel opportunities: 8 tasks in Foundational, 3 tasks in Polish
- MVP scope: Foundational + US1 + US2 (20 tasks)
