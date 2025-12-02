# Tasks: Processing Statistics and Metrics Tracking

**Input**: Design documents from `/specs/040-processing-stats/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Project initialization - no new files needed, extending existing modules

- [x] T001 Bump SCHEMA_VERSION from 17 to 18 in src/video_policy_orchestrator/db/schema.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data model extensions that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T002 [P] Add processing_stats table SQL to SCHEMA_SQL in src/video_policy_orchestrator/db/schema.py
- [x] T003 [P] Add action_results table SQL to SCHEMA_SQL in src/video_policy_orchestrator/db/schema.py
- [x] T004 [P] Add performance_metrics table SQL to SCHEMA_SQL in src/video_policy_orchestrator/db/schema.py
- [x] T005 Add migrate_v17_to_v18() function in src/video_policy_orchestrator/db/schema.py
- [x] T006 Update initialize_database() to call migrate_v17_to_v18() in src/video_policy_orchestrator/db/schema.py
- [x] T007 [P] Add ProcessingStatsRecord dataclass in src/video_policy_orchestrator/db/types.py
- [x] T008 [P] Add ActionResultRecord dataclass in src/video_policy_orchestrator/db/types.py
- [x] T009 [P] Add PerformanceMetricsRecord dataclass in src/video_policy_orchestrator/db/types.py
- [x] T010 [P] Add StatsSummary view model dataclass in src/video_policy_orchestrator/db/types.py
- [x] T011 [P] Add PolicyStats view model dataclass in src/video_policy_orchestrator/db/types.py
- [x] T012 [P] Add FileProcessingHistory view model dataclass in src/video_policy_orchestrator/db/types.py
- [x] T013 Add insert_processing_stats() CRUD function in src/video_policy_orchestrator/db/queries.py
- [x] T014 [P] Add insert_action_result() CRUD function in src/video_policy_orchestrator/db/queries.py
- [x] T015 [P] Add insert_performance_metric() CRUD function in src/video_policy_orchestrator/db/queries.py
- [x] T016 Add get_processing_stats_by_id() query function in src/video_policy_orchestrator/db/queries.py
- [x] T017 Add get_processing_stats_for_file() query function in src/video_policy_orchestrator/db/queries.py
- [x] T018 Add compute_partial_hash() helper function in src/video_policy_orchestrator/workflow/stats_capture.py
- [x] T019 Add count_tracks_by_type() helper function in src/video_policy_orchestrator/workflow/stats_capture.py
- [x] T020 Integrate statistics capture into V11WorkflowProcessor.process_file() in src/video_policy_orchestrator/workflow/v11_processor.py

**Checkpoint**: Foundation ready - statistics are now captured during processing

---

## Phase 3: User Story 1 - View Disk Space Savings (Priority: P1) MVP

**Goal**: Users can query total disk space saved and per-file savings after processing

**Independent Test**: Process a file, then run `vpo stats summary` to see size before/after metrics

### Implementation for User Story 1

- [x] T021 [US1] Add get_stats_summary() aggregate query function in src/video_policy_orchestrator/db/views.py
- [x] T022 [US1] Add get_recent_stats() query function in src/video_policy_orchestrator/db/views.py
- [x] T023 [US1] Create CLI stats command group in src/video_policy_orchestrator/cli/stats.py
- [x] T024 [US1] Implement `vpo stats summary` subcommand with --since/--until date filtering in src/video_policy_orchestrator/cli/stats.py
- [x] T025 [US1] Add table/json/csv output formatters for summary in src/video_policy_orchestrator/cli/stats.py
- [x] T026 [US1] Register stats command in src/video_policy_orchestrator/cli/__init__.py
- [x] T027 [US1] Add GET /api/stats/summary route handler in src/video_policy_orchestrator/server/ui/routes.py
- [x] T028 [US1] Add GET /api/stats/recent route handler in src/video_policy_orchestrator/server/ui/routes.py
- [x] T029 [US1] Create statistics dashboard template in src/video_policy_orchestrator/server/ui/templates/sections/stats.html
- [x] T030 [US1] Add stats dashboard route (GET /stats) in src/video_policy_orchestrator/server/ui/routes.py

**Checkpoint**: User Story 1 complete - users can view disk space savings via CLI and Web UI

---

## Phase 4: User Story 2 - Track Removed Content (Priority: P2)

**Goal**: Users can see track counts before/after and number removed per file

**Independent Test**: Process a file with multiple tracks, verify track removal counts in stats detail

### Implementation for User Story 2

- [x] T031 [US2] Add get_stats_detail() query with action_results join in src/video_policy_orchestrator/db/views.py
- [x] T032 [US2] Implement `vpo stats file <path>` subcommand in src/video_policy_orchestrator/cli/stats.py
- [x] T033 [US2] Implement `vpo stats detail <id>` subcommand in src/video_policy_orchestrator/cli/stats.py
- [x] T034 [US2] Add table formatter for track removal display in src/video_policy_orchestrator/cli/stats.py
- [x] T035 [US2] Add GET /api/stats/files/{file_id} route handler in src/video_policy_orchestrator/server/ui/routes.py
- [x] T036 [US2] Add GET /api/stats/{stats_id} route handler in src/video_policy_orchestrator/server/ui/routes.py
- [x] T037 [US2] Update stats dashboard template with track removal section in src/video_policy_orchestrator/server/ui/templates/sections/stats.html

**Checkpoint**: User Story 2 complete - users can view track removal details

---

## Phase 5: User Story 3 - Analyze Policy Effectiveness (Priority: P2)

**Goal**: Users can compare policies by savings and success rate

**Independent Test**: Process files with two different policies, run `vpo stats policy` to compare

### Implementation for User Story 3

- [x] T038 [US3] Add get_policy_stats() aggregate query function in src/video_policy_orchestrator/db/views.py
- [x] T039 [US3] Add get_policy_stats_by_name() query function in src/video_policy_orchestrator/db/views.py
- [x] T040 [US3] Implement `vpo stats policies` subcommand (list all) with --since/--until date filtering in src/video_policy_orchestrator/cli/stats.py
- [x] T041 [US3] Implement `vpo stats policy <name>` subcommand (single policy) in src/video_policy_orchestrator/cli/stats.py
- [x] T042 [US3] Add table formatter for policy comparison in src/video_policy_orchestrator/cli/stats.py
- [x] T043 [US3] Add GET /api/stats/policies route handler in src/video_policy_orchestrator/server/ui/routes.py
- [x] T044 [US3] Add GET /api/stats/policies/{name} route handler in src/video_policy_orchestrator/server/ui/routes.py
- [x] T045 [US3] Update stats dashboard template with policy comparison table in src/video_policy_orchestrator/server/ui/templates/sections/stats.html

**Checkpoint**: User Story 3 complete - users can compare policy effectiveness

---

## Phase 6: User Story 4 - Track Transcode Operations (Priority: P3)

**Goal**: Users can see codec transformations and skip reasons

**Independent Test**: Process a file with video transcode, verify codec info in stats detail

### Implementation for User Story 4

- [ ] T046 [US4] Capture video transcode info (source_codec, target_codec, skipped, skip_reason) in src/video_policy_orchestrator/workflow/v11_processor.py (DEFERRED - requires deeper phase executor integration)
- [ ] T047 [US4] Capture audio transcode summary (transcoded vs preserved counts) in src/video_policy_orchestrator/workflow/v11_processor.py (DEFERRED - requires deeper phase executor integration)
- [x] T048 [US4] Update stats detail formatter to display transcode info in src/video_policy_orchestrator/cli/stats.py
- [x] T049 [US4] Update stats dashboard template with transcode section in src/video_policy_orchestrator/server/static/js/stats.js

**Checkpoint**: User Story 4 partial - display scaffolding complete, capture integration deferred

---

## Phase 7: User Story 5 - View Processing Performance (Priority: P3)

**Goal**: Users can see wall-clock time per phase and identify bottlenecks

**Independent Test**: Process a file with multi-phase policy, verify per-phase timing in stats detail

### Implementation for User Story 5

- [x] T050 [US5] Capture per-phase wall_time_seconds in V11PhaseExecutor in src/video_policy_orchestrator/workflow/v11_processor.py (already implemented via PhaseMetrics)
- [x] T051 [US5] Insert performance_metrics records after each phase in src/video_policy_orchestrator/workflow/v11_processor.py (already implemented in stats_capture.py)
- [x] T052 [US5] Add get_performance_metrics_for_stats() query function in src/video_policy_orchestrator/db/queries.py
- [ ] T053 [US5] Parse FFmpeg encoding metrics (fps, bitrate) in transcode executor in src/video_policy_orchestrator/executor/transcode.py (DEFERRED - enhancement)
- [x] T054 [US5] Processing duration shown in `vpo stats detail` in src/video_policy_orchestrator/cli/stats.py
- [x] T055 [US5] Performance metrics display (duration, phases) in src/video_policy_orchestrator/cli/stats.py
- [x] T056 [US5] Performance section in stats dashboard modal in src/video_policy_orchestrator/server/static/js/stats.js

**Checkpoint**: User Story 5 mostly complete - basic timing captured, FFmpeg metrics deferred

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Purge capability, edge cases, documentation

- [x] T057 [P] Add delete_processing_stats_before() purge function in src/video_policy_orchestrator/db/queries.py
- [x] T058 [P] Add delete_processing_stats_by_policy() purge function in src/video_policy_orchestrator/db/queries.py (also added delete_all_processing_stats)
- [x] T059 Implement `vpo stats purge` subcommand with --before, --policy, --all, --dry-run flags in src/video_policy_orchestrator/cli/stats.py
- [x] T060 Add DELETE /api/stats/purge route handler in src/video_policy_orchestrator/server/ui/routes.py
- [x] T061 Handle edge case: partial stats on processing failure in src/video_policy_orchestrator/workflow/v11_processor.py (handled - stats persisted even on failure)
- [x] T062 Handle edge case: negative size_change (file size increase) display in src/video_policy_orchestrator/cli/stats.py
- [x] T063 Handle edge case: zero-change processing display in src/video_policy_orchestrator/cli/stats.py
- [x] T064 Add file integrity hash verification display (hash_before, hash_after) in src/video_policy_orchestrator/cli/stats.py
- [x] T065 Update CLAUDE.md with stats module documentation

**Checkpoint**: Phase 8 complete - all purge functionality implemented, edge cases handled, documentation updated

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational
- **User Story 2 (Phase 4)**: Depends on Foundational
- **User Story 3 (Phase 5)**: Depends on Foundational
- **User Story 4 (Phase 6)**: Depends on Foundational + US1 (for display infrastructure)
- **User Story 5 (Phase 7)**: Depends on Foundational + US1 (for display infrastructure)
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - no dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational - no dependencies on other stories
- **User Story 3 (P2)**: Can start after Foundational - no dependencies on other stories
- **User Story 4 (P3)**: Requires US1 CLI infrastructure for display
- **User Story 5 (P3)**: Requires US1 CLI infrastructure for display

### Within Each User Story

- Query functions before CLI/API implementations
- CLI before Web UI (can be parallelized if preferred)
- Core implementation before display formatting

### Parallel Opportunities

Within Phase 2 (Foundational):
- T002, T003, T004 can run in parallel (different table definitions)
- T007, T008, T009, T010, T011, T012 can run in parallel (different dataclasses)
- T014, T015 can run in parallel after T013 (different insert functions)

Within User Story phases:
- CLI and Web UI implementations can be parallelized per story

---

## Parallel Example: Phase 2 Foundational

```bash
# Launch all table definitions in parallel:
Task: "Add processing_stats table SQL to SCHEMA_SQL in src/video_policy_orchestrator/db/schema.py"
Task: "Add action_results table SQL to SCHEMA_SQL in src/video_policy_orchestrator/db/schema.py"
Task: "Add performance_metrics table SQL to SCHEMA_SQL in src/video_policy_orchestrator/db/schema.py"

# Launch all dataclasses in parallel:
Task: "Add ProcessingStatsRecord dataclass in src/video_policy_orchestrator/db/types.py"
Task: "Add ActionResultRecord dataclass in src/video_policy_orchestrator/db/types.py"
Task: "Add PerformanceMetricsRecord dataclass in src/video_policy_orchestrator/db/types.py"
Task: "Add StatsSummary view model dataclass in src/video_policy_orchestrator/db/types.py"
Task: "Add PolicyStats view model dataclass in src/video_policy_orchestrator/db/types.py"
Task: "Add FileProcessingHistory view model dataclass in src/video_policy_orchestrator/db/types.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Run `vpo stats summary` after processing a file
5. Deploy/demo if ready - users can now see disk space savings

### Incremental Delivery

1. Setup + Foundational → Statistics captured during processing
2. Add User Story 1 → `vpo stats summary` works → MVP Complete
3. Add User Story 2 → Track removal details visible
4. Add User Story 3 → Policy comparison works
5. Add User Stories 4 & 5 → Full metrics visible
6. Add Polish → Purge capability, edge cases handled

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Stories 1 & 4 (disk savings + transcode)
   - Developer B: User Stories 2 & 5 (track removal + performance)
   - Developer C: User Story 3 + Polish (policy comparison + purge)
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Statistics capture happens in Foundational phase; user stories add query/display capabilities
- Schema migration is additive-only (safe to roll back if needed)
- Avoid: modifying existing workflow behavior beyond adding statistics capture
