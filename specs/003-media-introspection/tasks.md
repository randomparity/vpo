# Tasks: Media Introspection & Track Modeling

**Input**: Design documents from `/specs/003-media-introspection/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Test fixtures are part of User Story 4 (P3). Unit/integration tests included as they support the feature's quality goals.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/video_policy_orchestrator/`, `tests/` at repository root
- Paths follow existing 002-library-scanner structure

---

## Phase 1: Setup

**Purpose**: Extend existing project structure for media introspection

- [x] T001 Create ffprobe fixtures directory at tests/fixtures/ffprobe/
- [x] T002 [P] Add IntrospectionResult dataclass to src/video_policy_orchestrator/db/models.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data model extensions that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Extend TrackInfo dataclass with audio fields (channels, channel_layout) in src/video_policy_orchestrator/db/models.py
- [x] T004 Extend TrackInfo dataclass with video fields (width, height, frame_rate) in src/video_policy_orchestrator/db/models.py
- [x] T005 Extend TrackRecord dataclass with new fields (channels, channel_layout, width, height, frame_rate) in src/video_policy_orchestrator/db/models.py
- [x] T006 Update tracks table schema with new columns in src/video_policy_orchestrator/db/schema.py
- [x] T007 Add schema migration function for existing databases in src/video_policy_orchestrator/db/schema.py
- [x] T008 Update insert_track function to handle new fields in src/video_policy_orchestrator/db/models.py
- [x] T009 Update get_tracks_for_file function to return new fields in src/video_policy_orchestrator/db/models.py
- [x] T010 Add TrackRecord.from_track_info conversion for new fields in src/video_policy_orchestrator/db/models.py

**Checkpoint**: Data model extensions complete - user story implementation can now begin

---

## Phase 3: User Story 1 - Track Enumeration (Priority: P1) MVP

**Goal**: Users can run `vpo inspect <file>` to see all tracks in a media file with their metadata

**Independent Test**: Run `vpo inspect movie.mkv` and verify formatted track list displays with ID, type, codec, language, title, default flag, resolution (video), and channels (audio)

### Implementation for User Story 1

- [x] T011 [US1] Create FFprobeIntrospector class skeleton in src/video_policy_orchestrator/introspector/ffprobe.py
- [x] T012 [US1] Implement is_available() static method using shutil.which in src/video_policy_orchestrator/introspector/ffprobe.py
- [x] T013 [US1] Implement _run_ffprobe() subprocess invocation in src/video_policy_orchestrator/introspector/ffprobe.py
- [x] T014 [US1] Implement _parse_streams() to extract track metadata from JSON in src/video_policy_orchestrator/introspector/ffprobe.py
- [x] T015 [US1] Implement _map_track_type() for codec_type to track_type conversion in src/video_policy_orchestrator/introspector/ffprobe.py
- [x] T016 [US1] Implement _map_channel_layout() for channel count to label conversion in src/video_policy_orchestrator/introspector/ffprobe.py
- [x] T017 [US1] Implement get_file_info() method per MediaIntrospector protocol in src/video_policy_orchestrator/introspector/ffprobe.py
- [x] T018 [US1] Export FFprobeIntrospector from src/video_policy_orchestrator/introspector/__init__.py
- [x] T019 [US1] Create inspect command skeleton in src/video_policy_orchestrator/cli/inspect.py
- [x] T020 [US1] Implement human-readable track output formatter in src/video_policy_orchestrator/cli/inspect.py
- [x] T021 [US1] Implement JSON output formatter in src/video_policy_orchestrator/cli/inspect.py
- [x] T022 [US1] Add --format option (human/json) to inspect command in src/video_policy_orchestrator/cli/inspect.py
- [x] T023 [US1] Handle ffprobe-not-found error with exit code 2 in src/video_policy_orchestrator/cli/inspect.py
- [x] T024 [US1] Handle file-not-found error with exit code 1 in src/video_policy_orchestrator/cli/inspect.py
- [x] T025 [US1] Handle parse-error with exit code 3 in src/video_policy_orchestrator/cli/inspect.py
- [x] T026 [US1] Register inspect command in CLI main group in src/video_policy_orchestrator/cli/__init__.py

**Checkpoint**: `vpo inspect <file>` displays track information - MVP complete

---

## Phase 4: User Story 2 - Track Data Persistence (Priority: P2)

**Goal**: Track metadata is stored in database during scan operations for policy rule targeting

**Independent Test**: Run `vpo scan <dir>`, then query `~/.vpo/library.db` and verify tracks table contains records with all metadata fields

### Implementation for User Story 2

- [x] T027 [US2] Implement upsert_tracks_for_file() with smart merge logic in src/video_policy_orchestrator/db/models.py
- [x] T028 [US2] Update scan orchestrator to use FFprobeIntrospector instead of stub in src/video_policy_orchestrator/scanner/orchestrator.py
- [x] T029 [US2] Integrate track persistence into scan workflow in src/video_policy_orchestrator/scanner/orchestrator.py
- [x] T030 [US2] Handle introspection errors during scan (log warning, continue) in src/video_policy_orchestrator/scanner/orchestrator.py

**Checkpoint**: `vpo scan` now extracts and persists track data to database

---

## Phase 5: User Story 3 - Robust Media Parsing (Priority: P2)

**Goal**: System handles edge cases gracefully: missing metadata, parse errors, unusual codecs

**Independent Test**: Run introspection against edge-case fixtures and verify no crashes, appropriate defaults applied

### Implementation for User Story 3

- [x] T031 [US3] Add default "und" language handling when tags.language missing in src/video_policy_orchestrator/introspector/ffprobe.py
- [x] T032 [US3] Add graceful handling for missing disposition field in src/video_policy_orchestrator/introspector/ffprobe.py
- [x] T033 [US3] Add graceful handling for missing video dimensions in src/video_policy_orchestrator/introspector/ffprobe.py
- [x] T034 [US3] Add graceful handling for missing audio channels in src/video_policy_orchestrator/introspector/ffprobe.py
- [x] T035 [US3] Add warnings collection to IntrospectionResult for non-fatal issues in src/video_policy_orchestrator/introspector/ffprobe.py
- [x] T036 [US3] Handle "no streams" case (empty tracks list, warning) in src/video_policy_orchestrator/introspector/ffprobe.py
- [x] T037 [US3] Handle non-UTF8 characters in metadata by sanitizing in src/video_policy_orchestrator/introspector/ffprobe.py
- [x] T038 [US3] Preserve uncommon codec identifiers as-is for policy matching in src/video_policy_orchestrator/introspector/ffprobe.py
- [x] T038a [US3] Log warning and skip if duplicate stream index encountered in src/video_policy_orchestrator/introspector/ffprobe.py

**Checkpoint**: Introspection handles all edge cases gracefully without crashes

---

## Phase 6: User Story 4 - Test Fixtures for Development (Priority: P3)

**Goal**: Sample ffprobe JSON fixtures available for testing without real media files

**Independent Test**: Load each fixture file and verify it parses correctly with expected track structures

### Implementation for User Story 4

- [x] T039 [P] [US4] Create simple_single_track.json fixture (1 video + 1 audio) in tests/fixtures/ffprobe/simple_single_track.json
- [x] T040 [P] [US4] Create multi_audio.json fixture (1 video + 3 audio tracks, different languages) in tests/fixtures/ffprobe/multi_audio.json
- [x] T041 [P] [US4] Create subtitle_heavy.json fixture (1 video + 1 audio + 5 subtitles) in tests/fixtures/ffprobe/subtitle_heavy.json
- [x] T042 [P] [US4] Create edge_case_missing_metadata.json fixture (missing language, title, disposition) in tests/fixtures/ffprobe/edge_case_missing_metadata.json
- [x] T043 [US4] Create fixture loader utility function in tests/conftest.py
- [x] T044 [US4] Write unit tests for FFprobeIntrospector._parse_streams() in tests/unit/test_ffprobe_introspector.py
- [x] T045 [US4] Write unit tests for channel layout mapping in tests/unit/test_ffprobe_introspector.py
- [x] T046 [US4] Write unit tests for track type mapping in tests/unit/test_ffprobe_introspector.py
- [x] T047 [US4] Write unit tests for edge case handling in tests/unit/test_ffprobe_introspector.py
- [x] T048 [US4] Write integration test for inspect command with fixtures in tests/integration/test_inspect_command.py

**Checkpoint**: All fixtures created, tests pass using fixtures

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final quality improvements across all stories

- [x] T049 [P] Update introspector __init__.py docstring to document available implementations in src/video_policy_orchestrator/introspector/__init__.py
- [x] T050 [P] Add type hints to all new functions in src/video_policy_orchestrator/introspector/ffprobe.py
- [x] T051 Run ruff check and fix any linting issues
- [x] T052 Run pytest and ensure all tests pass
- [x] T053 Verify quickstart.md examples work end-to-end
- [x] T054 Test ffprobe-not-installed error message on system without ffprobe

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational
- **User Story 2 (Phase 4)**: Depends on Foundational + US1 (uses FFprobeIntrospector)
- **User Story 3 (Phase 5)**: Depends on US1 (extends ffprobe.py)
- **User Story 4 (Phase 6)**: Depends on US1 (tests require implementation)
- **Polish (Phase 7)**: Depends on all user stories

### User Story Dependencies

- **User Story 1 (P1)**: After Foundational - No dependencies on other stories
- **User Story 2 (P2)**: After US1 - Uses FFprobeIntrospector from US1
- **User Story 3 (P2)**: After US1 - Extends edge case handling in ffprobe.py
- **User Story 4 (P3)**: After US1 - Tests require working implementation

### Within Each User Story

- T003-T010 (data model) before T011+ (implementation)
- T011-T018 (introspector) before T019-T026 (CLI)
- Core implementation before error handling
- Story complete before moving to next priority

### Parallel Opportunities

Within Phase 2 (Foundational):
- T003, T004 can run in parallel (different sections of TrackInfo)

Within Phase 3 (US1):
- T015, T016 can run in parallel (different helper methods)
- T020, T021 can run in parallel (different formatters)

Within Phase 6 (US4):
- T039, T040, T041, T042 can run in parallel (different fixture files)
- T044, T045, T046, T047 can run in parallel (different test files)

---

## Parallel Example: User Story 4 Fixtures

```bash
# Launch all fixture creation tasks together:
Task: "Create simple_single_track.json fixture in tests/fixtures/ffprobe/"
Task: "Create multi_audio.json fixture in tests/fixtures/ffprobe/"
Task: "Create subtitle_heavy.json fixture in tests/fixtures/ffprobe/"
Task: "Create edge_case_missing_metadata.json fixture in tests/fixtures/ffprobe/"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T010)
3. Complete Phase 3: User Story 1 (T011-T026)
4. **STOP and VALIDATE**: Test `vpo inspect movie.mkv`
5. MVP delivers: Users can inspect track metadata for any media file

### Incremental Delivery

1. Setup + Foundational → Data model ready
2. Add User Story 1 → `vpo inspect` works → Demo CLI inspection
3. Add User Story 2 → `vpo scan` persists tracks → Demo database queries
4. Add User Story 3 → Edge cases handled → Robust for production
5. Add User Story 4 → Tests + fixtures → CI/CD ready

### Single Developer Strategy

Execute in priority order:
1. Phase 1 + Phase 2 (foundation)
2. Phase 3: US1 (MVP)
3. Phase 4: US2 (persistence)
4. Phase 5: US3 (robustness)
5. Phase 6: US4 (tests)
6. Phase 7: Polish

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently testable after completion
- US2 and US3 both have P2 priority but US2 should complete first (US3 extends US1 edge cases)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
