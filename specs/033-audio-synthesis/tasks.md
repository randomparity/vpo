# Tasks: Audio Track Synthesis

**Input**: Design documents from `/specs/033-audio-synthesis/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Test tasks are included as this is a complex feature requiring verification.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## User Story Mapping

| Story ID | Title | Priority | Spec Reference |
|----------|-------|----------|----------------|
| US1 | EAC3 5.1 Compatibility Track Creation | P1 | User Story 1 |
| US2 | AAC Stereo Downmix Creation | P1 | User Story 2 |
| US3 | Intelligent Source Track Selection | P2 | User Story 3 |
| US4 | Multiple Synthesis Tracks | P2 | User Story 4 |
| US5 | Track Positioning Control | P3 | User Story 5 |
| US6 | Synthesis Dry-Run Preview | P3 | User Story 6 |
| US7 | Preserve Original Lossless Audio | P1 | User Story 7 (cross-cutting constraint) |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create module structure and shared types

- [ ] T001 Create synthesis module directory structure at src/video_policy_orchestrator/policy/synthesis/
- [ ] T002 [P] Create synthesis module __init__.py with public exports at src/video_policy_orchestrator/policy/synthesis/__init__.py
- [ ] T003 [P] Create custom exceptions (SynthesisError, EncoderUnavailableError) in src/video_policy_orchestrator/policy/synthesis/exceptions.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models and FFmpeg integration that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Create AudioCodec enum in src/video_policy_orchestrator/policy/synthesis/models.py
- [ ] T005 [P] Create ChannelConfig enum with channel count mapping in src/video_policy_orchestrator/policy/synthesis/models.py
- [ ] T006 [P] Create Position type (after_source, end, integer) in src/video_policy_orchestrator/policy/synthesis/models.py
- [ ] T007 Create SynthesisTrackDefinition dataclass in src/video_policy_orchestrator/policy/synthesis/models.py
- [ ] T008 [P] Create SourcePreferences and PreferenceCriterion dataclasses in src/video_policy_orchestrator/policy/synthesis/models.py
- [ ] T009 Create SourceTrackSelection dataclass in src/video_policy_orchestrator/policy/synthesis/models.py
- [ ] T010 Create SynthesisOperation dataclass in src/video_policy_orchestrator/policy/synthesis/models.py
- [ ] T011 [P] Create SynthesisPlan and SkippedSynthesis dataclasses in src/video_policy_orchestrator/policy/synthesis/models.py
- [ ] T012 [P] Create SkipReason enum in src/video_policy_orchestrator/policy/synthesis/models.py
- [ ] T013 Implement encoder availability detection in src/video_policy_orchestrator/policy/synthesis/encoders.py
- [ ] T014 Implement codec-to-FFmpeg-encoder mapping in src/video_policy_orchestrator/policy/synthesis/encoders.py
- [ ] T015 [P] Implement default bitrate lookup by codec and channel count in src/video_policy_orchestrator/policy/synthesis/encoders.py
- [ ] T016 Implement channel downmix filter generation (pan filters) in src/video_policy_orchestrator/policy/synthesis/downmix.py
- [ ] T017 [P] Implement channel layout normalization in src/video_policy_orchestrator/policy/synthesis/downmix.py
- [ ] T018 Extend PolicySchema with audio_synthesis section in src/video_policy_orchestrator/policy/schema.py
- [ ] T019 Add audio_synthesis YAML parsing and validation in src/video_policy_orchestrator/policy/schema.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - EAC3 5.1 Compatibility Track Creation (Priority: P1) MVP

**Goal**: Create EAC3 5.1 audio tracks from lossless surround sources

**Independent Test**: Apply policy to file with TrueHD 7.1, verify EAC3 5.1 track created

**Note**: US1 uses basic source selection (first matching audio track). Full preference-based scoring is implemented in US3 and integrated afterward.

### Tests for User Story 1

- [ ] T020 [P] [US1] Unit test for EAC3 encoder availability detection in tests/unit/policy/synthesis/test_encoders.py
- [ ] T021 [P] [US1] Unit test for 7.1→5.1 downmix filter generation in tests/unit/policy/synthesis/test_downmix.py

### Implementation for User Story 1

- [ ] T022 [US1] Implement FFmpegSynthesisExecutor class skeleton in src/video_policy_orchestrator/executor/ffmpeg_synthesis.py
- [ ] T023 [US1] Implement can_handle() for synthesis operations in src/video_policy_orchestrator/executor/ffmpeg_synthesis.py
- [ ] T024 [US1] Implement FFmpeg transcoding subprocess call with EAC3 encoding in src/video_policy_orchestrator/executor/ffmpeg_synthesis.py
- [ ] T025 [US1] Implement temp file creation and cleanup in src/video_policy_orchestrator/executor/ffmpeg_synthesis.py
- [ ] T026 [US1] Implement mkvmerge remux to add synthesized track in src/video_policy_orchestrator/executor/ffmpeg_synthesis.py
- [ ] T027 [US1] Implement atomic file swap with backup in src/video_policy_orchestrator/executor/ffmpeg_synthesis.py
- [ ] T027a [US1] Implement title inheritance (inherit from source or use custom) in src/video_policy_orchestrator/executor/ffmpeg_synthesis.py
- [ ] T027b [US1] Implement language tag inheritance (inherit from source or use custom) in src/video_policy_orchestrator/executor/ffmpeg_synthesis.py
- [ ] T028 [US1] Register FFmpegSynthesisExecutor in executor registry in src/video_policy_orchestrator/executor/__init__.py

**Checkpoint**: EAC3 5.1 synthesis works end-to-end

---

## Phase 4: User Story 2 - AAC Stereo Downmix Creation (Priority: P1)

**Goal**: Create AAC stereo tracks with proper surround-to-stereo downmix

**Independent Test**: Apply policy to file with 5.1 audio, verify AAC stereo track created with correct downmix

### Tests for User Story 2

- [ ] T029 [P] [US2] Unit test for 5.1→stereo downmix filter in tests/unit/policy/synthesis/test_downmix.py
- [ ] T030 [P] [US2] Unit test for AAC encoder parameters in tests/unit/policy/synthesis/test_encoders.py

### Implementation for User Story 2

- [ ] T031 [US2] Extend FFmpegSynthesisExecutor to support AAC encoding in src/video_policy_orchestrator/executor/ffmpeg_synthesis.py
- [ ] T032 [US2] Implement stereo downmix filter chain application in src/video_policy_orchestrator/executor/ffmpeg_synthesis.py
- [ ] T033 [US2] Add bitrate parameter handling for AAC in src/video_policy_orchestrator/executor/ffmpeg_synthesis.py

**Checkpoint**: AAC stereo synthesis with downmix works

---

## Phase 5: User Story 3 - Intelligent Source Track Selection (Priority: P2)

**Goal**: Select best source track based on language, commentary exclusion, and channel preferences

**Independent Test**: Apply policy to multi-track file, verify correct source selected

### Tests for User Story 3

- [ ] T034 [P] [US3] Unit test for language preference scoring in tests/unit/policy/synthesis/test_source_selector.py
- [ ] T035 [P] [US3] Unit test for commentary detection heuristics in tests/unit/policy/synthesis/test_source_selector.py
- [ ] T036 [P] [US3] Unit test for channel count preference (max) in tests/unit/policy/synthesis/test_source_selector.py
- [ ] T037 [P] [US3] Unit test for fallback to first audio track in tests/unit/policy/synthesis/test_source_selector.py

### Implementation for User Story 3

- [ ] T038 [US3] Implement source track scoring algorithm in src/video_policy_orchestrator/policy/synthesis/source_selector.py
- [ ] T039 [US3] Implement language matching with und fallback in src/video_policy_orchestrator/policy/synthesis/source_selector.py
- [ ] T040 [US3] Implement commentary detection from track title in src/video_policy_orchestrator/policy/synthesis/source_selector.py
- [ ] T041 [US3] Implement channel count preference handling in src/video_policy_orchestrator/policy/synthesis/source_selector.py
- [ ] T042 [US3] Implement fallback behavior with warning logging in src/video_policy_orchestrator/policy/synthesis/source_selector.py
- [ ] T043 [US3] Implement select_source_track() main function in src/video_policy_orchestrator/policy/synthesis/source_selector.py

**Checkpoint**: Source selection algorithm fully functional

---

## Phase 6: User Story 4 - Multiple Synthesis Tracks (Priority: P2)

**Goal**: Process multiple synthesis definitions in single policy execution

**Independent Test**: Apply policy with 2+ synthesis tracks, verify all created

### Tests for User Story 4

- [ ] T044 [P] [US4] Unit test for multiple synthesis track planning in tests/unit/policy/synthesis/test_planner.py
- [ ] T045 [P] [US4] Unit test for partial skip (some conditions not met) in tests/unit/policy/synthesis/test_planner.py

### Implementation for User Story 4

- [ ] T046 [US4] Implement SynthesisPlanner class in src/video_policy_orchestrator/policy/synthesis/planner.py
- [ ] T047 [US4] Implement iterate-and-evaluate for multiple track definitions in src/video_policy_orchestrator/policy/synthesis/planner.py
- [ ] T048 [US4] Implement condition evaluation delegation to existing conditions.py in src/video_policy_orchestrator/policy/synthesis/planner.py
- [ ] T049 [US4] Implement SynthesisPlan building with operations and skipped lists in src/video_policy_orchestrator/policy/synthesis/planner.py
- [ ] T050 [US4] Extend FFmpegSynthesisExecutor to process multiple operations sequentially in src/video_policy_orchestrator/executor/ffmpeg_synthesis.py

**Checkpoint**: Multiple synthesis tracks work in single pass

---

## Phase 7: User Story 5 - Track Positioning Control (Priority: P3)

**Goal**: Place synthesized tracks at specified positions (after_source, end, index)

**Independent Test**: Apply policies with different positions, verify track order

### Tests for User Story 5

- [ ] T051 [P] [US5] Unit test for after_source position resolution in tests/unit/policy/synthesis/test_planner.py
- [ ] T052 [P] [US5] Unit test for end position resolution in tests/unit/policy/synthesis/test_planner.py
- [ ] T053 [P] [US5] Unit test for integer position resolution in tests/unit/policy/synthesis/test_planner.py
- [ ] T054 [P] [US5] Unit test for position adjustment with multiple inserts in tests/unit/policy/synthesis/test_planner.py

### Implementation for User Story 5

- [ ] T055 [US5] Implement position resolution algorithm in src/video_policy_orchestrator/policy/synthesis/planner.py
- [ ] T056 [US5] Implement track index adjustment for sequential inserts in src/video_policy_orchestrator/policy/synthesis/planner.py
- [ ] T057 [US5] Implement final_track_order projection in SynthesisPlan in src/video_policy_orchestrator/policy/synthesis/planner.py
- [ ] T058 [US5] Implement mkvmerge track ordering arguments in src/video_policy_orchestrator/executor/ffmpeg_synthesis.py

**Checkpoint**: Track positioning fully functional

---

## Phase 8: User Story 6 - Synthesis Dry-Run Preview (Priority: P3)

**Goal**: Show synthesis plan in dry-run without modifying files

**Independent Test**: Run with --dry-run, verify output shows plan, no files modified

### Tests for User Story 6

- [ ] T059 [P] [US6] Unit test for dry-run output formatting in tests/unit/policy/synthesis/test_planner.py
- [ ] T060 [P] [US6] Unit test for skip reason formatting in tests/unit/policy/synthesis/test_planner.py

### Implementation for User Story 6

- [ ] T061 [US6] Implement format_synthesis_plan() for CLI output in src/video_policy_orchestrator/policy/synthesis/planner.py
- [ ] T062 [US6] Implement format_final_track_order() display in src/video_policy_orchestrator/policy/synthesis/planner.py
- [ ] T063 [US6] Integrate synthesis plan display into apply command dry-run in src/video_policy_orchestrator/cli/apply.py
- [ ] T064 [US6] Ensure executor respects dry_run flag (no execution) in src/video_policy_orchestrator/executor/ffmpeg_synthesis.py

**Checkpoint**: Dry-run shows complete synthesis plan

---

## Phase 9: User Story 7 - Preserve Original Lossless Audio (Priority: P1 - Cross-cutting)

**Goal**: Guarantee original tracks are never modified or removed

**Independent Test**: Verify original tracks unchanged after synthesis

### Tests for User Story 7

- [ ] T065 [P] [US7] Integration test verifying original track preservation in tests/integration/executor/test_ffmpeg_synthesis.py
- [ ] T066 [P] [US7] Unit test for backup/restore on failure in tests/unit/executor/test_ffmpeg_synthesis.py

### Implementation for User Story 7

- [ ] T067 [US7] Implement backup creation before any file modification in src/video_policy_orchestrator/executor/ffmpeg_synthesis.py
- [ ] T068 [US7] Implement SIGINT handler for clean cancellation in src/video_policy_orchestrator/executor/ffmpeg_synthesis.py
- [ ] T069 [US7] Implement temp file cleanup on any error in src/video_policy_orchestrator/executor/ffmpeg_synthesis.py
- [ ] T070 [US7] Add structured logging for all synthesis operations in src/video_policy_orchestrator/executor/ffmpeg_synthesis.py

**Checkpoint**: Original audio preservation guaranteed

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, edge cases, and quality improvements

- [ ] T071 [P] Update docs/usage/ with audio synthesis policy examples
- [ ] T072 [P] Add encoder unavailability error handling with clear message in src/video_policy_orchestrator/executor/ffmpeg_synthesis.py
- [ ] T073 [P] Add upmix detection and skip with warning in src/video_policy_orchestrator/policy/synthesis/planner.py
- [ ] T074 Validate quickstart.md scenarios work end-to-end
- [ ] T075 [P] Add integration test with real audio fixtures in tests/integration/executor/test_ffmpeg_synthesis.py
- [ ] T076 Run full test suite and fix any regressions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-9)**: All depend on Foundational phase completion
  - US1 (EAC3) and US2 (AAC) can proceed in parallel
  - US3 (Source Selection) can proceed independently
  - US4 (Multiple Tracks) depends on US1/US2 for executor
  - US5 (Positioning) depends on US4 for planner
  - US6 (Dry-Run) depends on US4/US5 for plan formatting
  - US7 (Preservation) can proceed in parallel with US1-US6
- **Polish (Phase 10)**: Depends on all user stories complete

### User Story Dependencies

```
Phase 2 (Foundational)
    │
    ├─→ US1 (EAC3) ──────┬─→ US4 (Multiple) ──→ US5 (Position) ──→ US6 (Dry-Run)
    │                    │
    ├─→ US2 (AAC) ───────┘
    │
    ├─→ US3 (Source Selection) ──→ [integrates with US1-US6]
    │
    └─→ US7 (Preservation) ──→ [cross-cutting verification]
```

**Source Selection Note**:
- US1/US2 implement basic source selection (first audio track matching minimum channel requirement)
- US3 adds full preference scoring algorithm (language, commentary, channel count)
- After US3, the planner integrates scoring into US1/US2 flows automatically

### Parallel Opportunities

**Within Phase 2 (Foundational)**:
- T004-T012 (models) can be parallelized by file
- T013-T017 (encoders, downmix) can be parallelized

**User Stories in Parallel**:
- US1 + US2 + US3 + US7 can all start after Phase 2
- Test tasks within each story marked [P] can run in parallel

---

## Parallel Example: Phase 2 Models

```bash
# Launch all model definitions together:
Task: "Create AudioCodec enum in src/video_policy_orchestrator/policy/synthesis/models.py"
Task: "Create ChannelConfig enum in src/video_policy_orchestrator/policy/synthesis/models.py"
Task: "Create Position type in src/video_policy_orchestrator/policy/synthesis/models.py"
Task: "Create SkipReason enum in src/video_policy_orchestrator/policy/synthesis/models.py"
```

## Parallel Example: US3 Tests

```bash
# Launch all source selector tests together:
Task: "Unit test for language preference scoring in tests/unit/policy/synthesis/test_source_selector.py"
Task: "Unit test for commentary detection heuristics in tests/unit/policy/synthesis/test_source_selector.py"
Task: "Unit test for channel count preference (max) in tests/unit/policy/synthesis/test_source_selector.py"
Task: "Unit test for fallback to first audio track in tests/unit/policy/synthesis/test_source_selector.py"
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: US1 - EAC3 5.1 Creation
4. **STOP and VALIDATE**: Test EAC3 synthesis independently
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (EAC3) + US2 (AAC) → Basic synthesis works (MVP!)
3. Add US3 (Source Selection) → Smart source picking
4. Add US4 (Multiple Tracks) → Full batch capability
5. Add US5 (Positioning) + US6 (Dry-Run) → User experience polish
6. Verify US7 (Preservation) throughout → Safety guarantee

### Recommended Execution Path

```
Phase 1 → Phase 2 → US1 → US2 → US3 → US4 → US5 → US6 → verify US7 → Phase 10
```

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- US7 (Preservation) is verified by integration tests, not separate implementation
