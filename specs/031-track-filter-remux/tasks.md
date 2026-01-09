# Tasks: Track Filtering & Container Remux

**Input**: Design documents from `/specs/031-track-filter-remux/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Test tasks included as this feature modifies critical file operations.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md structure:
- Source: `src/vpo/`
- Tests: `tests/unit/`, `tests/integration/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and foundational model additions

- [X] T001 Add custom exceptions InsufficientTracksError and IncompatibleCodecError in src/vpo/policy/exceptions.py
- [X] T002 [P] Add MP4_INCOMPATIBLE_CODECS constant set in src/vpo/policy/models.py
- [X] T003 [P] Update MAX_SCHEMA_VERSION to 3 in src/vpo/policy/loader.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core models and infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Add LanguageFallbackConfig frozen dataclass in src/vpo/policy/models.py
- [X] T005 [P] Add AudioFilterConfig frozen dataclass in src/vpo/policy/models.py
- [X] T006 [P] Add SubtitleFilterConfig frozen dataclass in src/vpo/policy/models.py
- [X] T007 [P] Add AttachmentFilterConfig frozen dataclass in src/vpo/policy/models.py
- [X] T008 [P] Add ContainerConfig frozen dataclass in src/vpo/policy/models.py
- [X] T009 Add TrackDisposition frozen dataclass in src/vpo/policy/models.py
- [X] T010 [P] Add ContainerChange frozen dataclass in src/vpo/policy/models.py
- [X] T011 Extend PolicySchema dataclass with v3 fields (audio_filter, subtitle_filter, attachment_filter, container) in src/vpo/policy/models.py
- [X] T012 Extend Plan dataclass with track_dispositions, container_change, tracks_removed, tracks_kept fields in src/vpo/policy/models.py
- [X] T013 Add Pydantic validation models for v3 fields (AudioFilterModel, SubtitleFilterModel, etc.) in src/vpo/policy/loader.py
- [X] T014 Update policy loading to parse v3 fields in _parse_policy_dict() in src/vpo/policy/loader.py
- [X] T015 Add v3 field validation (reject v3 fields if schema_version < 3) in src/vpo/policy/loader.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Remove Non-Preferred Audio Tracks (Priority: P1)

**Goal**: Enable users to filter audio tracks by language, keeping only preferred languages while ensuring at least one audio track remains.

**Independent Test**: Apply policy with `audio_filter.languages: [eng, und]` to multi-language file and verify only matching tracks are marked for removal while minimum audio requirement is enforced.

### Tests for User Story 1

- [X] T016 [P] [US1] Unit test for audio track filtering logic in tests/unit/policy/test_track_filtering.py
- [X] T017 [P] [US1] Unit test for minimum audio track validation in tests/unit/policy/test_track_filtering.py
- [X] T018 [P] [US1] Unit test for InsufficientTracksError scenarios in tests/unit/policy/test_track_filtering.py

### Implementation for User Story 1

- [X] T019 [US1] Implement _evaluate_audio_track() helper function in src/vpo/policy/evaluator.py
- [X] T020 [US1] Implement compute_track_dispositions() for audio tracks in src/vpo/policy/evaluator.py
- [X] T021 [US1] Add audio track minimum validation with InsufficientTracksError in src/vpo/policy/evaluator.py
- [X] T022 [US1] Update evaluate_policy() to call compute_track_dispositions() when audio_filter present in src/vpo/policy/evaluator.py
- [X] T023 [US1] Extend MkvmergeExecutor with --audio-tracks selection in src/vpo/executor/mkvmerge.py
- [X] T024 [US1] Add _build_track_selection_args() method to MkvmergeExecutor in src/vpo/executor/mkvmerge.py
- [X] T025 [US1] Integration test for audio filtering end-to-end in tests/integration/test_track_filtering.py

**Checkpoint**: Audio track filtering fully functional and testable independently

---

## Phase 4: User Story 2 - Dry-Run Preview for Track Changes (Priority: P1)

**Goal**: Show detailed track-by-track disposition in dry-run output so users can verify policy correctness before applying.

**Independent Test**: Run `vpo apply --dry-run` with track filtering policy and verify output shows each track with KEEP/REMOVE action and reason.

### Tests for User Story 2

- [X] T026 [P] [US2] Unit test for _format_track_dispositions() output in tests/unit/cli/test_apply.py
- [X] T027 [P] [US2] Unit test for JSON dry-run output format in tests/unit/cli/test_apply.py

### Implementation for User Story 2

- [X] T028 [US2] Implement _format_track_dispositions() helper function in src/vpo/cli/apply.py
- [X] T029 [US2] Implement _format_container_change() helper function in src/vpo/cli/apply.py
- [X] T030 [US2] Update _format_dry_run_output() to include track dispositions in src/vpo/cli/apply.py
- [X] T031 [US2] Add summary line with tracks kept/removed count in src/vpo/cli/apply.py
- [X] T032 [US2] Implement JSON dry-run output format for --json flag in src/vpo/cli/apply.py
- [X] T033 [US2] Integration test for dry-run output with track filtering in tests/integration/test_apply_command.py

**Checkpoint**: Dry-run preview fully functional with track disposition details

---

## Phase 5: User Story 3 - Container Conversion to MKV (Priority: P2)

**Goal**: Convert AVI, MOV, and other containers to MKV format losslessly using mkvmerge.

**Independent Test**: Apply policy with `container.target: mkv` to AVI file and verify all streams preserved without re-encoding.

### Tests for User Story 3

- [X] T034 [P] [US3] Unit test for ContainerConfig validation in tests/unit/policy/test_container_config.py
- [X] T035 [P] [US3] Unit test for MKV container compatibility (all codecs supported) in tests/unit/policy/test_container_config.py

### Implementation for User Story 3

- [X] T036 [US3] Implement _evaluate_container_change() function in src/vpo/policy/evaluator.py
- [X] T037 [US3] Update evaluate_policy() to compute container_change when container config present in src/vpo/policy/evaluator.py
- [X] T038 [US3] Add skip-if-same-format logic (no remux if already MKV) in src/vpo/policy/evaluator.py
- [X] T039 [US3] Extend MkvmergeExecutor to handle input files of any format in src/vpo/executor/mkvmerge.py
- [X] T040 [US3] Integration test for AVI to MKV conversion in tests/integration/test_container_conversion.py

**Checkpoint**: MKV container conversion fully functional

---

## Phase 6: User Story 4 - Container Conversion to MP4 (Priority: P2)

**Goal**: Convert MKV files to MP4 format losslessly using FFmpeg with codec compatibility checking.

**Independent Test**: Apply policy with `container.target: mp4` to MKV with compatible codecs and verify lossless conversion with faststart flag.

### Tests for User Story 4

- [X] T041 [P] [US4] Unit test for MP4 codec compatibility checking in tests/unit/policy/test_container_config.py
- [X] T042 [P] [US4] Unit test for IncompatibleCodecError scenarios in tests/unit/policy/test_container_config.py
- [X] T043 [P] [US4] Unit test for on_incompatible_codec modes (error, skip) in tests/unit/policy/test_container_config.py

### Implementation for User Story 4

- [X] T044 [US4] Implement is_mp4_compatible() function in src/vpo/policy/evaluator.py
- [X] T045 [US4] Add MP4 codec compatibility checking to _evaluate_container_change() in src/vpo/policy/evaluator.py
- [X] T046 [US4] Implement on_incompatible_codec error mode with IncompatibleCodecError in src/vpo/policy/evaluator.py
- [X] T047 [US4] Implement on_incompatible_codec skip mode in src/vpo/policy/evaluator.py
- [X] T048 [US4] Create FFmpegRemuxExecutor class in src/vpo/executor/ffmpeg_remux.py
- [X] T049 [US4] Implement can_handle() method checking for MP4 target in src/vpo/executor/ffmpeg_remux.py
- [X] T050 [US4] Implement execute() method with -c copy and -movflags +faststart in src/vpo/executor/ffmpeg_remux.py
- [X] T051 [US4] Add FFmpegRemuxExecutor to executor registry in src/vpo/executor/__init__.py
- [X] T052 [US4] Integration test for MKV to MP4 conversion in tests/integration/test_container_conversion.py
- [X] T053 [US4] Integration test for incompatible codec error handling in tests/integration/test_container_conversion.py

> **Scope Note**: `on_incompatible_codec: transcode` mode is deferred to Sprint 3/4 per spec assumptions. Tasks T041-T053 implement `error` and `skip` modes only.

**Checkpoint**: MP4 container conversion fully functional with compatibility checking

---

## Phase 7: User Story 5 - Remove Non-Preferred Subtitle Tracks (Priority: P3)

**Goal**: Filter subtitle tracks by language with option to preserve forced subtitles regardless of language.

**Independent Test**: Apply policy with `subtitle_filter.languages: [eng]` and `preserve_forced: true` to multi-subtitle file and verify only matching + forced tracks remain.

### Tests for User Story 5

- [X] T054 [P] [US5] Unit test for subtitle language filtering in tests/unit/policy/test_track_filtering.py
- [X] T055 [P] [US5] Unit test for preserve_forced logic in tests/unit/policy/test_track_filtering.py
- [X] T056 [P] [US5] Unit test for remove_all subtitles option in tests/unit/policy/test_track_filtering.py

### Implementation for User Story 5

- [X] T057 [US5] Implement _evaluate_subtitle_track() helper function in src/vpo/policy/evaluator.py
- [X] T058 [US5] Add preserve_forced logic to subtitle evaluation (second pass re-add) in src/vpo/policy/evaluator.py
- [X] T059 [US5] Update compute_track_dispositions() to handle subtitle filtering in src/vpo/policy/evaluator.py
- [X] T060 [US5] Extend MkvmergeExecutor with --subtitle-tracks selection in src/vpo/executor/mkvmerge.py
- [X] T061 [US5] Integration test for subtitle filtering with forced preservation in tests/integration/test_track_filtering.py

**Checkpoint**: Subtitle track filtering fully functional

---

## Phase 8: User Story 6 - Remove Attachment Tracks (Priority: P3)

**Goal**: Remove attachment tracks (fonts, cover art) with warning when styled subtitles may be affected.

**Independent Test**: Apply policy with `attachment_filter.remove_all: true` to MKV with fonts and ASS subtitles, verify attachments removed and warning shown.

### Tests for User Story 6

- [X] T062 [P] [US6] Unit test for attachment removal in tests/unit/policy/test_track_filtering.py
- [X] T063 [P] [US6] Unit test for font warning when ASS/SSA subtitles present in tests/unit/policy/test_track_filtering.py

### Implementation for User Story 6

- [X] T064 [US6] Implement _evaluate_attachment_track() helper function in src/vpo/policy/evaluator.py
- [X] T065 [US6] Implement _detect_styled_subtitles() helper to find ASS/SSA tracks in src/vpo/policy/evaluator.py
- [X] T066 [US6] Add font removal warning when styled subtitles detected in src/vpo/policy/evaluator.py
- [X] T067 [US6] Update compute_track_dispositions() to handle attachment filtering in src/vpo/policy/evaluator.py
- [X] T068 [US6] Extend MkvmergeExecutor with --no-attachments flag in src/vpo/executor/mkvmerge.py
- [X] T069 [US6] Integration test for attachment removal with warning in tests/integration/test_track_filtering.py

**Checkpoint**: Attachment track removal fully functional with font warnings

---

## Phase 9: User Story 7 - Language Fallback Logic (Priority: P3)

**Goal**: Implement fallback modes (content_language, keep_all, keep_first, error) for when preferred languages aren't found.

**Independent Test**: Apply policy with `audio_filter.fallback.mode: content_language` to file with only Japanese audio (no English) and verify Japanese kept as content language.

### Tests for User Story 7

- [X] T070 [P] [US7] Unit test for fallback mode content_language in tests/unit/policy/test_track_filtering.py
- [X] T071 [P] [US7] Unit test for fallback mode keep_all in tests/unit/policy/test_track_filtering.py
- [X] T072 [P] [US7] Unit test for fallback mode keep_first in tests/unit/policy/test_track_filtering.py
- [X] T073 [P] [US7] Unit test for fallback mode error in tests/unit/policy/test_track_filtering.py
- [X] T074 [P] [US7] Unit test for minimum track count enforcement in tests/unit/policy/test_track_filtering.py

### Implementation for User Story 7

- [X] T075 [US7] Implement _detect_content_language() helper function in src/vpo/policy/evaluator.py
- [X] T076 [US7] Implement _apply_fallback() function for all modes in src/vpo/policy/evaluator.py
- [X] T077 [US7] Integrate fallback logic into audio track filtering in src/vpo/policy/evaluator.py
- [X] T078 [US7] Add minimum track count validation with fallback trigger in src/vpo/policy/evaluator.py
- [X] T079 [US7] Integration test for fallback modes end-to-end in tests/integration/test_track_filtering.py

**Checkpoint**: Language fallback logic fully functional

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T080 [P] Add v2 backward compatibility tests in tests/unit/policy/test_loader.py
- [X] T081 [P] Add CLI error handling for InsufficientTracksError with suggestions in src/vpo/cli/apply.py
- [X] T082 [P] Add CLI error handling for IncompatibleCodecError with suggestions in src/vpo/cli/apply.py
- [X] T083 [P] Add disk space pre-flight check before remux operations in src/vpo/executor/mkvmerge.py
- [X] T083a [P] Verify backup creation in MkvmergeExecutor.execute() follows existing pattern in src/vpo/executor/mkvmerge.py
- [X] T083b [P] Add backup creation to FFmpegRemuxExecutor.execute() in src/vpo/executor/ffmpeg_remux.py
- [X] T084 Update policy documentation with v3 schema fields in docs/usage/policies.md
- [X] T085 [P] Add example v3 policy files in docs/examples/
- [X] T086 Run full test suite and verify all tests pass
- [X] T087 Run quickstart.md validation steps

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-9)**: All depend on Foundational phase completion
  - US1 and US2 are both P1 and can proceed in parallel
  - US3 and US4 are both P2 and can proceed in parallel (after P1)
  - US5, US6, US7 are all P3 and can proceed in parallel (after P2)
- **Polish (Phase 10)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational - Depends on TrackDisposition model from US1 implementation
- **User Story 3 (P2)**: Can start after Foundational - No dependencies on other stories
- **User Story 4 (P2)**: Can start after Foundational - Requires ContainerConfig from Phase 2
- **User Story 5 (P3)**: Can start after Foundational - Similar pattern to US1
- **User Story 6 (P3)**: Can start after Foundational - Similar pattern to US1
- **User Story 7 (P3)**: Can start after Foundational - Integrates with US1 audio filtering

### Within Each User Story

- Tests SHOULD be written first (TDD approach)
- Helper functions before main logic
- Evaluator logic before executor integration
- Unit tests before integration tests

### Parallel Opportunities

- **Phase 1**: T002, T003 can run in parallel
- **Phase 2**: T005-T008, T010 can run in parallel (config models)
- **Phase 3**: T016-T018 tests can run in parallel
- **Phase 4**: T026-T027 tests can run in parallel
- **Phase 5**: T034-T035 tests can run in parallel
- **Phase 6**: T041-T043 tests can run in parallel
- **Phase 7**: T054-T056 tests can run in parallel
- **Phase 8**: T062-T063 tests can run in parallel
- **Phase 9**: T070-T074 tests can run in parallel
- **Phase 10**: T080-T083, T085 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Unit test for audio track filtering logic in tests/unit/policy/test_track_filtering.py"
Task: "Unit test for minimum audio track validation in tests/unit/policy/test_track_filtering.py"
Task: "Unit test for InsufficientTracksError scenarios in tests/unit/policy/test_track_filtering.py"
```

## Parallel Example: Phase 2 Models

```bash
# Launch all config models in parallel:
Task: "Add AudioFilterConfig frozen dataclass in src/vpo/policy/models.py"
Task: "Add SubtitleFilterConfig frozen dataclass in src/vpo/policy/models.py"
Task: "Add AttachmentFilterConfig frozen dataclass in src/vpo/policy/models.py"
Task: "Add ContainerConfig frozen dataclass in src/vpo/policy/models.py"
Task: "Add ContainerChange frozen dataclass in src/vpo/policy/models.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Audio filtering)
4. Complete Phase 4: User Story 2 (Dry-run preview)
5. **STOP and VALIDATE**: Test audio filtering with dry-run preview
6. Deploy/demo MVP - users can now filter audio tracks with preview

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 + US2 → Test independently → **MVP Release** (audio filtering + dry-run)
3. Add US3 + US4 → Test independently → **Release** (container conversion)
4. Add US5 + US6 + US7 → Test independently → **Full Release** (all filters + fallback)

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (audio filtering)
   - Developer B: User Story 2 (dry-run output)
3. After P1 complete:
   - Developer A: User Story 3 (MKV conversion)
   - Developer B: User Story 4 (MP4 conversion)
4. After P2 complete:
   - Developer A: User Story 5 (subtitle filtering)
   - Developer B: User Story 6 (attachment removal)
   - Developer C: User Story 7 (fallback logic)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- US1 and US2 together form the MVP (audio filtering with preview)
