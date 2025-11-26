# Tasks: Conditional Video Transcoding

**Input**: Design documents from `/specs/034-conditional-video-transcode/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Test tasks included as this is a complex feature with many edge cases requiring validation.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US9)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md, this is a single project extending existing VPO structure:
- Source: `src/video_policy_orchestrator/`
- Tests: `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare project for conditional transcoding implementation

- [x] T001 Review existing TranscodeExecutor in src/video_policy_orchestrator/executor/transcode.py
- [x] T002 [P] Review existing policy models in src/video_policy_orchestrator/policy/models.py
- [x] T003 [P] Review existing ffmpeg tool detection in src/video_policy_orchestrator/tools/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models and enums that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Add QualityMode enum (crf, bitrate, constrained_quality) in src/video_policy_orchestrator/policy/models.py
- [x] T005 [P] Add ScaleAlgorithm enum (lanczos, bicubic, bilinear) in src/video_policy_orchestrator/policy/models.py
- [x] T006 [P] Add HardwareAccelMode enum (auto, nvenc, qsv, vaapi, none) in src/video_policy_orchestrator/policy/models.py
- [x] T007 Add VideoTranscodeConfig dataclass (target_codec, skip_if, quality, scaling, hw_accel) in src/video_policy_orchestrator/policy/models.py
- [x] T008 [P] Add TranscodeResult dataclass (skipped, skip_reason, video_action, audio_actions, encoder) in src/video_policy_orchestrator/policy/models.py
- [x] T009 [P] Add VideoTranscodeAction dataclass in src/video_policy_orchestrator/policy/models.py
- [x] T010 Update policy schema parsing to handle new transcode.video section in src/video_policy_orchestrator/policy/loader.py
- [x] T011 Add bitrate parsing utility function (parse "10M", "5000k" to int) in src/video_policy_orchestrator/policy/models.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Skip Transcoding for Compliant Files (Priority: P1) MVP

**Goal**: Skip re-encoding files that already meet codec/resolution/bitrate requirements

**Independent Test**: Apply transcode policy to HEVC file with skip_if codec_matches: [hevc] → verify "Skipping video transcode - already compliant"

### Tests for User Story 1

- [x] T012 [P] [US1] Unit test for SkipCondition dataclass in tests/unit/test_skip_conditions.py
- [x] T013 [P] [US1] Unit test for should_skip_transcode() function in tests/unit/test_skip_conditions.py
- [x] T014 [P] [US1] Unit test for codec_matches evaluation (case-insensitive) in tests/unit/test_skip_conditions.py
- [x] T015 [P] [US1] Unit test for resolution_within evaluation in tests/unit/test_skip_conditions.py
- [x] T016 [P] [US1] Unit test for bitrate_under evaluation in tests/unit/test_skip_conditions.py
- [x] T017 [P] [US1] Unit test for AND logic (all conditions must pass) in tests/unit/test_skip_conditions.py

### Implementation for User Story 1

- [x] T018 [US1] Add SkipCondition dataclass (codec_matches, resolution_within, bitrate_under) in src/video_policy_orchestrator/policy/models.py
- [x] T019 [US1] Add resolution_within_threshold() helper function in src/video_policy_orchestrator/executor/transcode.py
- [x] T020 [US1] Implement should_skip_transcode(file_info, skip_if) function in src/video_policy_orchestrator/executor/transcode.py
- [x] T021 [US1] Integrate skip evaluation in TranscodeExecutor.execute() in src/video_policy_orchestrator/executor/transcode.py
- [x] T022 [US1] Add dry-run skip message "Skipping video transcode - already compliant" in src/video_policy_orchestrator/executor/transcode.py
- [x] T023 [US1] Parse skip_if section from YAML policy in src/video_policy_orchestrator/policy/loader.py

**Checkpoint**: Skip conditions fully functional - files meeting criteria are not re-encoded

---

## Phase 4: User Story 2 - Configure CRF Quality Settings (Priority: P1)

**Goal**: Enable CRF-based quality control with codec-appropriate defaults

**Independent Test**: Apply policy with quality.mode: crf, quality.crf: 20 → verify ffmpeg uses -crf 20

### Tests for User Story 2

- [x] T024 [P] [US2] Unit test for QualitySettings dataclass validation in tests/unit/test_quality_settings.py
- [x] T025 [P] [US2] Unit test for CRF range validation (0-51) in tests/unit/test_quality_settings.py
- [x] T026 [P] [US2] Unit test for codec-specific CRF defaults in tests/unit/test_quality_settings.py

### Implementation for User Story 2

- [x] T027 [US2] Add QualitySettings dataclass (mode, crf, preset, tune, bitrate fields) in src/video_policy_orchestrator/policy/models.py
- [x] T028 [US2] Add get_default_crf(codec) function returning codec-appropriate defaults in src/video_policy_orchestrator/policy/models.py
- [x] T029 [US2] Add CRF validation (0-51 range) in QualitySettings in src/video_policy_orchestrator/policy/models.py
- [x] T030 [US2] Update build_ffmpeg_command() to use quality.crf in src/video_policy_orchestrator/executor/transcode.py
- [x] T031 [US2] Parse quality section from YAML policy in src/video_policy_orchestrator/policy/loader.py

**Checkpoint**: CRF quality mode functional with validation and defaults

---

## Phase 5: User Story 8 - Preserve Audio During Video Transcode (Priority: P1)

**Goal**: Stream-copy lossless audio while transcoding video, preserve track order and subtitles

**Independent Test**: Transcode file with TrueHD audio using preserve_codecs: [truehd] → verify TrueHD unchanged via ffprobe

### Tests for User Story 8

- [x] T032 [P] [US8] Unit test for AudioTranscodeConfig dataclass in tests/unit/test_audio_preservation.py
- [x] T033 [P] [US8] Unit test for preserve_codecs matching in tests/unit/test_audio_preservation.py
- [x] T034 [P] [US8] Unit test for audio track planning (COPY vs TRANSCODE) in tests/unit/test_audio_preservation.py

### Implementation for User Story 8

- [x] T035 [US8] Add AudioTranscodeConfig dataclass (preserve_codecs, transcode_to, transcode_bitrate) in src/video_policy_orchestrator/policy/models.py
- [x] T036 [US8] Enhance plan_audio_track() with preserve_codecs logic in src/video_policy_orchestrator/policy/transcode.py
- [x] T037 [US8] Update build_ffmpeg_command() to stream-copy preserved codecs in src/video_policy_orchestrator/executor/transcode.py
- [x] T038 [US8] Ensure subtitle tracks always use -c:s copy in src/video_policy_orchestrator/executor/transcode.py
- [x] T039 [US8] Parse audio section from YAML policy in src/video_policy_orchestrator/policy/loader.py

**Checkpoint**: Audio preservation functional - lossless codecs stream-copied, lossy transcoded

---

## Phase 6: User Story 3 - Select Encoding Preset (Priority: P2)

**Goal**: Allow preset selection for speed/compression tradeoff

**Independent Test**: Apply policy with quality.preset: slow → verify ffmpeg uses -preset slow

### Tests for User Story 3

- [ ] T040 [P] [US3] Unit test for preset validation in tests/unit/test_quality_settings.py
- [ ] T041 [P] [US3] Unit test for default preset (medium) in tests/unit/test_quality_settings.py

### Implementation for User Story 3

- [ ] T042 [US3] Add VALID_PRESETS constant with all 9 preset names in src/video_policy_orchestrator/policy/models.py
- [ ] T043 [US3] Add preset validation in QualitySettings in src/video_policy_orchestrator/policy/models.py
- [ ] T044 [US3] Update build_ffmpeg_command() to use quality.preset in src/video_policy_orchestrator/executor/transcode.py

**Checkpoint**: Preset selection functional with validation

---

## Phase 7: User Story 5 - Downscale Resolution (Priority: P2)

**Goal**: Enable resolution downscaling with aspect ratio preservation

**Independent Test**: Apply policy with scaling.max_resolution: 1080p to 4K file → verify output is 1920x1080

### Tests for User Story 5

- [ ] T045 [P] [US5] Unit test for ScalingSettings dataclass in tests/unit/test_scaling.py
- [ ] T046 [P] [US5] Unit test for resolution preset to dimensions mapping in tests/unit/test_scaling.py
- [ ] T047 [P] [US5] Unit test for aspect ratio preservation calculation in tests/unit/test_scaling.py
- [ ] T048 [P] [US5] Unit test for upscale=false behavior in tests/unit/test_scaling.py

### Implementation for User Story 5

- [ ] T049 [US5] Add ScalingSettings dataclass (max_resolution, max_width, max_height, algorithm, upscale) in src/video_policy_orchestrator/policy/models.py
- [ ] T050 [US5] Add RESOLUTION_MAP constant (480p-8k dimensions) in src/video_policy_orchestrator/policy/models.py
- [ ] T051 [US5] Add calculate_scaled_dimensions() function preserving aspect ratio in src/video_policy_orchestrator/executor/transcode.py
- [ ] T052 [US5] Update build_ffmpeg_command() to add -vf scale filter in src/video_policy_orchestrator/executor/transcode.py
- [ ] T053 [US5] Parse scaling section from YAML policy in src/video_policy_orchestrator/policy/schema.py

**Checkpoint**: Resolution scaling functional with aspect ratio preservation

---

## Phase 8: User Story 7 - Use Hardware Acceleration (Priority: P2)

**Goal**: Auto-detect and use hardware encoders (NVENC, QSV, VAAPI)

**Independent Test**: Apply policy with hardware_acceleration.enabled: auto on NVIDIA system → verify hevc_nvenc used

### Tests for User Story 7

- [ ] T054 [P] [US7] Unit test for HardwareAccelConfig dataclass in tests/unit/test_hardware_accel.py
- [ ] T055 [P] [US7] Unit test for encoder detection (mock ffmpeg -encoders) in tests/unit/test_hardware_accel.py
- [ ] T056 [P] [US7] Unit test for fallback_to_cpu behavior in tests/unit/test_hardware_accel.py

### Implementation for User Story 7

- [ ] T057 [US7] Add HardwareAccelConfig dataclass (enabled, fallback_to_cpu) in src/video_policy_orchestrator/policy/models.py
- [ ] T058 [US7] Add detect_available_encoders() with LRU cache in src/video_policy_orchestrator/tools/ffmpeg.py
- [ ] T059 [US7] Add select_encoder(target_codec, hw_config) function in src/video_policy_orchestrator/executor/transcode.py
- [ ] T060 [US7] Update build_ffmpeg_command() to use selected encoder in src/video_policy_orchestrator/executor/transcode.py
- [ ] T061 [US7] Add encoder selection to dry-run output in src/video_policy_orchestrator/executor/transcode.py
- [ ] T062 [US7] Parse hardware_acceleration section from YAML policy in src/video_policy_orchestrator/policy/schema.py

**Checkpoint**: Hardware acceleration functional with auto-detection and fallback

---

## Phase 9: User Story 4 - Specify Video Tune Options (Priority: P3)

**Goal**: Enable content-specific tune options (film, animation, grain)

**Independent Test**: Apply policy with quality.tune: animation → verify ffmpeg uses -tune animation

### Tests for User Story 4

- [ ] T063 [P] [US4] Unit test for tune validation per encoder in tests/unit/test_quality_settings.py
- [ ] T064 [P] [US4] Unit test for invalid tune rejection in tests/unit/test_quality_settings.py

### Implementation for User Story 4

- [ ] T065 [US4] Add VALID_TUNES constant per encoder type in src/video_policy_orchestrator/policy/models.py
- [ ] T066 [US4] Add tune validation in QualitySettings in src/video_policy_orchestrator/policy/models.py
- [ ] T067 [US4] Update build_ffmpeg_command() to use quality.tune in src/video_policy_orchestrator/executor/transcode.py

**Checkpoint**: Tune options functional with per-encoder validation

---

## Phase 10: User Story 6 - Target Specific Bitrate (Priority: P3)

**Goal**: Enable bitrate targeting mode for predictable file sizes

**Independent Test**: Apply policy with quality.mode: bitrate, quality.bitrate: 5M → verify ffmpeg uses -b:v 5M

### Tests for User Story 6

- [ ] T068 [P] [US6] Unit test for bitrate mode validation in tests/unit/test_quality_settings.py
- [ ] T069 [P] [US6] Unit test for constrained_quality mode (CRF + max_bitrate) in tests/unit/test_quality_settings.py

### Implementation for User Story 6

- [ ] T070 [US6] Add bitrate validation in QualitySettings in src/video_policy_orchestrator/policy/models.py
- [ ] T071 [US6] Update build_ffmpeg_command() for bitrate mode (-b:v flag) in src/video_policy_orchestrator/executor/transcode.py
- [ ] T072 [US6] Update build_ffmpeg_command() for constrained_quality mode (-crf + -maxrate) in src/video_policy_orchestrator/executor/transcode.py

**Checkpoint**: Bitrate targeting functional with constrained quality support

---

## Phase 11: User Story 9 - View Transcoding Progress (Priority: P3)

**Goal**: Display progress percentage, frame count, ETA, and speed during transcode

**Independent Test**: Start transcode job → verify progress updates show percentage and ETA

### Tests for User Story 9

- [ ] T073 [P] [US9] Unit test for progress percentage calculation in tests/unit/test_transcode_progress.py
- [ ] T074 [P] [US9] Unit test for ETA calculation accuracy in tests/unit/test_transcode_progress.py

### Implementation for User Story 9

- [ ] T075 [US9] Verify FFmpegProgress parsing includes frame, fps, speed fields in src/video_policy_orchestrator/jobs/progress.py
- [ ] T076 [US9] Add calculate_eta() method to FFmpegProgress in src/video_policy_orchestrator/jobs/progress.py
- [ ] T077 [US9] Wire progress_callback in TranscodeExecutor to job system in src/video_policy_orchestrator/executor/transcode.py
- [ ] T078 [US9] Add progress display in CLI output in src/video_policy_orchestrator/cli/apply.py
- [ ] T079 [US9] Add progress endpoint/display in web UI in src/video_policy_orchestrator/server/routes.py

**Checkpoint**: Progress reporting functional in CLI and web UI

---

## Phase 12: Output Handling (Cross-Cutting)

**Purpose**: Implement temp file workflow, atomic replacement, cleanup, and verification

**Independent Test**: Start transcode, kill mid-process → verify temp file cleaned up, original unchanged

### Tests for Output Handling

- [ ] T080 [P] Unit test for temp file path generation in tests/unit/test_output_handling.py
- [ ] T081 [P] Unit test for atomic file replacement in tests/unit/test_output_handling.py
- [ ] T082 [P] Unit test for cleanup on failure in tests/unit/test_output_handling.py
- [ ] T083 [P] Unit test for integrity verification in tests/unit/test_output_handling.py

### Implementation for Output Handling

- [ ] T084 Add generate_temp_output_path() function in src/video_policy_orchestrator/executor/transcode.py
- [ ] T085 Add verify_transcode_integrity(output_path) function (ffprobe check, size > 0) in src/video_policy_orchestrator/executor/transcode.py
- [ ] T086 Add atomic_replace_original(temp_path, original_path) function in src/video_policy_orchestrator/executor/transcode.py
- [ ] T087 Add cleanup_temp_file(temp_path) in finally block of TranscodeExecutor.execute() in src/video_policy_orchestrator/executor/transcode.py
- [ ] T088 Wire temp→verify→replace→cleanup flow in TranscodeExecutor.execute() in src/video_policy_orchestrator/executor/transcode.py

**Checkpoint**: Output handling complete - temp file workflow safe and atomic

---

## Phase 13: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, and integration testing

- [ ] T089 [P] Add example transcode policies to docs/usage/ or examples/
- [ ] T090 [P] Update CLAUDE.md with new transcode policy options
- [ ] T091 Integration test: Skip + CRF + audio preservation in tests/integration/test_transcode_executor.py
- [ ] T092 Integration test: Scaling + hardware accel in tests/integration/test_transcode_executor.py
- [ ] T093 Add policy validation for conflicting options (e.g., CRF + bitrate mode)
- [ ] T094 Run quickstart.md validation scenarios

### Edge Case Handling

- [ ] T095 Edge case: Handle VFR input gracefully (detect via ffprobe, warn user) in src/video_policy_orchestrator/executor/transcode.py
- [ ] T096 Edge case: Handle missing bitrate metadata with warning in src/video_policy_orchestrator/executor/transcode.py
- [ ] T097 Edge case: Handle corrupted source files (catch ffmpeg errors, report clearly) in src/video_policy_orchestrator/executor/transcode.py
- [ ] T098 Edge case: Detect insufficient disk space before transcode (estimate output size) in src/video_policy_orchestrator/executor/transcode.py
- [ ] T099 Edge case: Handle multiple video streams (select primary, warn about others) in src/video_policy_orchestrator/executor/transcode.py
- [ ] T100 Edge case: Handle HW encoder memory errors with CPU fallback in src/video_policy_orchestrator/executor/transcode.py
- [ ] T101 Edge case: Preserve HDR metadata during downscaling, warn about compatibility in src/video_policy_orchestrator/executor/transcode.py

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phases 3-11)**: All depend on Foundational completion
  - US1 (P1), US2 (P1), US8 (P1) are highest priority - complete first
  - US3 (P2), US5 (P2), US7 (P2) can follow
  - US4 (P3), US6 (P3), US9 (P3) are lowest priority
- **Output Handling (Phase 12)**: Can start after Phase 2; integrates with TranscodeExecutor
- **Polish (Phase 13)**: Depends on all user stories and output handling being complete

### User Story Dependencies

- **US1 (Skip)**: Independent - no dependencies on other stories
- **US2 (CRF)**: Independent - core quality setting
- **US8 (Audio)**: Independent - audio handling
- **US3 (Preset)**: Depends on US2 (builds on QualitySettings)
- **US5 (Scaling)**: Independent - parallel with US3
- **US7 (HW Accel)**: Independent - parallel with US3, US5
- **US4 (Tune)**: Depends on US3 (extends QualitySettings)
- **US6 (Bitrate)**: Depends on US2 (extends QualitySettings)
- **US9 (Progress)**: Independent - existing infrastructure

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services
- Services/functions before executor integration
- Schema parsing last

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel
- Tests within each user story marked [P] can run in parallel
- US1, US2, US8 can all start in parallel after Foundational
- US3, US5, US7 can all start in parallel after P1 stories
- US4, US6, US9 can all start in parallel after P2 stories

---

## Parallel Example: P1 User Stories

```bash
# After Foundational complete, launch all P1 stories in parallel:

# US1: Skip Conditions
Task: "Unit test for SkipCondition dataclass in tests/unit/test_skip_conditions.py"
Task: "Unit test for should_skip_transcode() function in tests/unit/test_skip_conditions.py"

# US2: CRF Quality (parallel with US1)
Task: "Unit test for QualitySettings dataclass validation in tests/unit/test_quality_settings.py"
Task: "Unit test for CRF range validation (0-51) in tests/unit/test_quality_settings.py"

# US8: Audio Preservation (parallel with US1, US2)
Task: "Unit test for AudioTranscodeConfig dataclass in tests/unit/test_audio_preservation.py"
Task: "Unit test for preserve_codecs matching in tests/unit/test_audio_preservation.py"
```

---

## Implementation Strategy

### MVP First (P1 Stories Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: US1 - Skip Conditions
4. Complete Phase 4: US2 - CRF Quality
5. Complete Phase 5: US8 - Audio Preservation
6. **STOP and VALIDATE**: Test all P1 stories independently
7. Deploy/demo if ready - MVP complete!

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add P1 stories (US1, US2, US8) → Test → MVP!
3. Add P2 stories (US3, US5, US7) → Test → Enhanced release
4. Add P3 stories (US4, US6, US9) → Test → Full feature
5. Polish → Production ready

### Parallel Team Strategy

With 3 developers after Foundational:
- Developer A: US1 (Skip) → US4 (Tune) → US9 (Progress)
- Developer B: US2 (CRF) → US3 (Preset) → US6 (Bitrate)
- Developer C: US8 (Audio) → US5 (Scaling) → US7 (HW Accel)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- This feature extends existing TranscodeExecutor - review existing code first
