# Tasks: V9 Policy Editor GUI

**Input**: Design documents from `/specs/036-v9-policy-editor/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: No test tasks included (not explicitly requested in specification). Manual browser testing will be used as per plan.md.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md structure:
- Backend: `src/video_policy_orchestrator/`
- Frontend JS: `src/video_policy_orchestrator/server/static/js/policy-editor/`
- Frontend CSS: `src/video_policy_orchestrator/server/static/css/`
- Templates: `src/video_policy_orchestrator/server/ui/templates/sections/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Foundation components required by all user stories

- [ ] T001 Create accordion.js component in src/video_policy_orchestrator/server/static/js/policy-editor/accordion.js
- [ ] T002 [P] Add accordion CSS styles in src/video_policy_orchestrator/server/static/css/policy-editor.css
- [ ] T003 Update policy_editor.html template structure with accordion sections in src/video_policy_orchestrator/server/ui/templates/sections/policy_editor.html
- [ ] T004 Update policy-editor.js main module to import and initialize accordion in src/video_policy_orchestrator/server/static/js/policy-editor/policy-editor.js

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data model extensions that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

**Note**: T005-T009 all modify editor.py - implement sequentially or as a single combined task to avoid merge conflicts.

- [ ] T005 Extend PolicyRoundTripEditor with V3 field accessors (audio_filter, subtitle_filter, attachment_filter, container) in src/video_policy_orchestrator/policy/editor.py
- [ ] T006 Extend PolicyRoundTripEditor with V4 field accessors (conditional) in src/video_policy_orchestrator/policy/editor.py
- [ ] T007 Extend PolicyRoundTripEditor with V5 field accessors (audio_synthesis) in src/video_policy_orchestrator/policy/editor.py
- [ ] T008 Extend PolicyRoundTripEditor with V6 field accessors (transcode.video, transcode.audio) in src/video_policy_orchestrator/policy/editor.py
- [ ] T009 Extend PolicyRoundTripEditor with V9 field accessors (workflow) in src/video_policy_orchestrator/policy/editor.py
- [ ] T010 Extend api_policy_get handler to return all V3-V10 fields in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T011 Extend api_policy_put handler to accept and validate all V3-V10 fields in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T012 Extend api_policy_validate handler for V3-V10 field validation in src/video_policy_orchestrator/server/ui/routes.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Edit V6 Video Transcode Settings (Priority: P1) - MVP

**Goal**: Users can configure video transcoding settings (target_codec, skip_if, quality, scaling, hardware_acceleration) through the GUI

**Independent Test**: Create/edit policy with video transcode settings, verify YAML output matches expectations

### Implementation for User Story 1

- [ ] T013 [US1] Create section-transcode.js module skeleton in src/video_policy_orchestrator/server/static/js/policy-editor/section-transcode.js
- [ ] T014 [US1] Add video transcode HTML section to policy_editor.html template in src/video_policy_orchestrator/server/ui/templates/sections/policy_editor.html
- [ ] T015 [US1] Implement target_codec dropdown with validation in section-transcode.js
- [ ] T016 [US1] Implement skip_if subsection (codec_matches list, resolution_within dropdown, bitrate_under input) in section-transcode.js
- [ ] T017 [US1] Implement quality subsection (mode dropdown, crf input, bitrate input, preset dropdown, tune dropdown, two_pass checkbox) in section-transcode.js
- [ ] T018 [US1] Implement scaling subsection (max_resolution dropdown, max_width/max_height inputs, algorithm dropdown, upscale checkbox) in section-transcode.js
- [ ] T019 [US1] Implement hardware_acceleration subsection (enabled dropdown, fallback_to_cpu checkbox) in section-transcode.js
- [ ] T020 [US1] Add quality mode cross-field validation (bitrate required when mode=bitrate, crf+bitrate conflict detection) in section-transcode.js
- [ ] T021 [US1] Wire section-transcode.js to main policy-editor.js for state management and YAML preview updates

**Checkpoint**: Video transcode settings can be configured through GUI - MVP complete

---

## Phase 4: User Story 2 - Edit V6 Audio Transcode Settings (Priority: P1)

**Goal**: Users can configure audio transcoding settings (preserve_codecs, transcode_to, transcode_bitrate) through the GUI

**Independent Test**: Edit audio transcode settings and verify YAML output

### Implementation for User Story 2

- [ ] T022 [US2] Add audio transcode HTML section (within transcode accordion) to policy_editor.html template
- [ ] T023 [US2] Implement preserve_codecs list with add/remove controls in section-transcode.js
- [ ] T024 [US2] Implement transcode_to dropdown and transcode_bitrate input with validation in section-transcode.js
- [ ] T025 [US2] Add bitrate format validation (pattern: \d+(\.\d+)?[kKmM]) in section-transcode.js

**Checkpoint**: Audio transcode settings can be configured through GUI

---

## Phase 5: User Story 5 - Edit V3 Track Filtering Configuration (Priority: P2)

**Goal**: Users can configure audio_filter, subtitle_filter, and attachment_filter through the GUI

**Independent Test**: Configure filtering settings and verify YAML output

### Implementation for User Story 5

- [ ] T026 [US5] Create section-filters.js module in src/video_policy_orchestrator/server/static/js/policy-editor/section-filters.js
- [ ] T027 [P] [US5] Add track filters HTML section to policy_editor.html template
- [ ] T028 [US5] Implement audio_filter subsection (languages list, fallback_mode dropdown, minimum input) in section-filters.js
- [ ] T029 [US5] Implement V10 audio_filter options (keep_music_tracks, keep_sfx_tracks, keep_non_speech_tracks and exclude_* checkboxes) in section-filters.js
- [ ] T030 [US5] Implement subtitle_filter subsection (languages list, preserve_forced checkbox, remove_all checkbox) in section-filters.js
- [ ] T031 [US5] Implement attachment_filter subsection (remove_all checkbox) in section-filters.js
- [ ] T032 [US5] Add language code validation (ISO 639-2/B pattern: 2-3 lowercase letters) in section-filters.js
- [ ] T033 [US5] Wire section-filters.js to main policy-editor.js

**Checkpoint**: Track filtering can be configured through GUI

---

## Phase 6: User Story 4 - Edit V4 Conditional Rules (Priority: P2)

**Goal**: Users can configure conditional rules with condition builder (2-level nesting) and action selectors through the GUI

**Independent Test**: Create conditional rule with when condition and then/else actions, verify YAML output

### Implementation for User Story 4

- [ ] T034 [US4] Create section-conditional.js module in src/video_policy_orchestrator/server/static/js/policy-editor/section-conditional.js
- [ ] T035 [P] [US4] Add conditional rules HTML section to policy_editor.html template
- [ ] T036 [US4] Implement rule list UI with add/remove rule controls in section-conditional.js
- [ ] T037 [US4] Implement condition type selector (exists, count, and, or, not, audio_is_multi_language) in section-conditional.js
- [ ] T038 [US4] Implement exists condition builder (track_type dropdown + filter fields: language, codec, is_default, is_forced, channels, width, height, title, not_commentary) in section-conditional.js
- [ ] T039 [US4] Implement count condition builder (track_type + filters + count operator + value) in section-conditional.js
- [ ] T040 [US4] Implement boolean condition builder (and/or with sub-condition list, max 2 levels) in section-conditional.js
- [ ] T041 [US4] Implement not condition builder (wraps single sub-condition) in section-conditional.js
- [ ] T042 [US4] Implement audio_is_multi_language condition (V7: track_index, threshold, primary_language) in section-conditional.js
- [ ] T043 [US4] Implement action selector (skip_video_transcode, skip_audio_transcode, skip_track_filter, warn, fail) in section-conditional.js
- [ ] T044 [US4] Implement V7 actions (set_forced, set_default with track_type, language, value) in section-conditional.js
- [ ] T045 [US4] Implement then_actions and else_actions list editors in section-conditional.js
- [ ] T046 [US4] Add 2-level nesting depth enforcement (disable boolean operators in sub-conditions) in section-conditional.js
- [ ] T047 [US4] Wire section-conditional.js to main policy-editor.js

**Checkpoint**: Conditional rules can be configured through GUI

---

## Phase 7: User Story 3 - Edit V5 Audio Synthesis Configuration (Priority: P2)

**Goal**: Users can configure audio synthesis tracks with source preferences and skip_if_exists through the GUI

**Independent Test**: Add synthesis track definition and verify YAML output

### Implementation for User Story 3

- [ ] T048 [US3] Create section-synthesis.js module in src/video_policy_orchestrator/server/static/js/policy-editor/section-synthesis.js
- [ ] T049 [P] [US3] Add audio synthesis HTML section to policy_editor.html template
- [ ] T050 [US3] Implement synthesis track list UI with add/remove track controls in section-synthesis.js
- [ ] T051 [US3] Implement track basic fields (name input, codec dropdown, channels dropdown/input) in section-synthesis.js
- [ ] T052 [US3] Implement source_prefer criteria list with add/remove (language, not_commentary, channels, codec) in section-synthesis.js
- [ ] T053 [US3] Implement optional fields (bitrate input, title dropdown/input, language dropdown/input, position dropdown/input) in section-synthesis.js
- [ ] T054 [US3] Implement skip_if_exists subsection (V8: codec list, channels with comparison operator dropdown + value input, language list, not_commentary checkbox) in section-synthesis.js
- [ ] T055 [US3] Add synthesis track name validation (non-empty, no path separators) in section-synthesis.js
- [ ] T056 [US3] Wire section-synthesis.js to main policy-editor.js

**Checkpoint**: Audio synthesis can be configured through GUI

---

## Phase 8: User Story 6 - Edit V3 Container Configuration (Priority: P3)

**Goal**: Users can configure container format conversion (target, on_incompatible_codec) through the GUI

**Independent Test**: Set container target and verify YAML output

### Implementation for User Story 6

- [ ] T057 [US6] Create section-container.js module in src/video_policy_orchestrator/server/static/js/policy-editor/section-container.js
- [ ] T058 [P] [US6] Add container HTML section to policy_editor.html template
- [ ] T059 [US6] Implement container target dropdown (mkv, mp4) in section-container.js
- [ ] T060 [US6] Implement on_incompatible_codec dropdown (error, skip, transcode) in section-container.js
- [ ] T061 [US6] Wire section-container.js to main policy-editor.js

**Checkpoint**: Container configuration can be configured through GUI

---

## Phase 9: User Story 7 - Edit V9 Workflow Configuration (Priority: P3)

**Goal**: Users can configure workflow settings (phases, auto_process, on_error) through the GUI

**Independent Test**: Configure workflow phases and verify YAML output

### Implementation for User Story 7

- [ ] T062 [US7] Create section-workflow.js module in src/video_policy_orchestrator/server/static/js/policy-editor/section-workflow.js
- [ ] T063 [P] [US7] Add workflow HTML section to policy_editor.html template
- [ ] T064 [US7] Implement phases selector (checkboxes for analyze, apply, transcode with reordering) in section-workflow.js
- [ ] T065 [US7] Implement auto_process toggle checkbox in section-workflow.js
- [ ] T066 [US7] Implement on_error dropdown (skip, continue, fail) in section-workflow.js
- [ ] T067 [US7] Wire section-workflow.js to main policy-editor.js

**Checkpoint**: Workflow configuration can be configured through GUI

---

## Phase 10: User Story 8 - Create New Policy (Priority: P3)

**Goal**: Users can create new policies through the GUI with schema_version 10

**Independent Test**: Create new policy via GUI and verify policy file is created

### Implementation for User Story 8

- [ ] T068 [US8] Add POST /api/policies endpoint handler for new policy creation in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T069 [US8] Add "Create New Policy" button to policies list page in src/video_policy_orchestrator/server/ui/templates/sections/policies.html
- [ ] T070 [US8] Implement new policy dialog/form (name input, initial settings) in src/video_policy_orchestrator/server/static/js/policies.js
- [ ] T071 [US8] Add duplicate policy name validation (409 Conflict response) in api route handler
- [ ] T072 [US8] Set default schema_version to MAX_SCHEMA_VERSION (10) for new policies

**Checkpoint**: New policies can be created through GUI

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T073 [P] Add debounced YAML preview updates (300ms) in policy-editor.js (Note: Each section's "Wire to main policy-editor.js" task must trigger preview updates on field changes)
- [ ] T074 [P] Implement field-level error display with CSS styling in policy-editor.css
- [ ] T075 [P] Add concurrent modification detection UI (conflict dialog) in policy-editor.js
- [ ] T076 [P] Add unknown field preservation warning banner in policy_editor.html
- [ ] T077 Update policy-editor.md documentation with V3-V10 features in docs/usage/policy-editor.md
- [ ] T078 Manual browser testing validation (all user stories)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-10)**: All depend on Foundational phase completion
  - User stories can then proceed in priority order (P1 → P2 → P3)
  - Within same priority, stories can run in parallel
- **Polish (Phase 11)**: Depends on at least MVP (User Story 1) being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational - Uses same section-transcode.js as US1
- **User Story 5 (P2)**: Can start after Foundational - Independent
- **User Story 4 (P2)**: Can start after Foundational - Independent (most complex)
- **User Story 3 (P2)**: Can start after Foundational - Independent
- **User Story 6 (P3)**: Can start after Foundational - Independent
- **User Story 7 (P3)**: Can start after Foundational - Independent
- **User Story 8 (P3)**: Can start after Foundational - Requires API route extension

### Within Each User Story

- HTML template section before JavaScript implementation
- Core field implementation before validation
- Section module complete before wiring to main editor

### Parallel Opportunities

**Setup Phase**:
- T001 and T002 can run in parallel (different files)

**Foundational Phase**:
- T005-T009 can run in parallel (same file but different methods)
- T010-T012 can run in parallel with T005-T009 (different file)

**User Story Implementation**:
- Template tasks ([P] marked) can run alongside JS implementation
- Different user story phases can run in parallel once Foundational is complete

---

## Parallel Example: Foundational Phase

```bash
# Launch all PolicyRoundTripEditor extensions together:
Task: "Extend PolicyRoundTripEditor with V3 field accessors"
Task: "Extend PolicyRoundTripEditor with V4 field accessors"
Task: "Extend PolicyRoundTripEditor with V5 field accessors"
Task: "Extend PolicyRoundTripEditor with V6 field accessors"
Task: "Extend PolicyRoundTripEditor with V9 field accessors"

# Launch API handler extensions together:
Task: "Extend api_policy_get handler to return all V3-V10 fields"
Task: "Extend api_policy_put handler to accept and validate all V3-V10 fields"
Task: "Extend api_policy_validate handler for V3-V10 field validation"
```

## Parallel Example: P2 User Stories

```bash
# After Foundational is complete, launch P2 stories in parallel:

# Developer A - User Story 5 (Track Filtering):
Task: "Create section-filters.js module"
Task: "Add track filters HTML section"
Task: "Implement audio_filter subsection"

# Developer B - User Story 4 (Conditional Rules):
Task: "Create section-conditional.js module"
Task: "Add conditional rules HTML section"
Task: "Implement condition type selector"

# Developer C - User Story 3 (Audio Synthesis):
Task: "Create section-synthesis.js module"
Task: "Add audio synthesis HTML section"
Task: "Implement synthesis track list UI"
```

---

## Implementation Strategy

### MVP First (User Stories 1 & 2 Only)

1. Complete Phase 1: Setup (accordion component)
2. Complete Phase 2: Foundational (API extensions)
3. Complete Phase 3: User Story 1 (Video Transcode)
4. Complete Phase 4: User Story 2 (Audio Transcode)
5. **STOP and VALIDATE**: Test transcode editing independently
6. Deploy/demo if ready - users can now configure V6 transcode via GUI

### Incremental Delivery

1. **MVP**: Setup + Foundational + US1 + US2 → V6 Transcode editing
2. **+Filtering**: Add US5 → V3 Track filtering
3. **+Conditional**: Add US4 → V4 Conditional rules
4. **+Synthesis**: Add US3 → V5 Audio synthesis
5. **+Container**: Add US6 → V3 Container conversion
6. **+Workflow**: Add US7 → V9 Workflow configuration
7. **+Create**: Add US8 → New policy creation
8. **Polish**: Phase 11 improvements

### Priority Rationale

- **P1 (US1, US2)**: V6 transcode is most complex and commonly requested feature
- **P2 (US3, US4, US5)**: Powerful features that benefit advanced users
- **P3 (US6, US7, US8)**: Lower frequency use cases, simpler implementation

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
