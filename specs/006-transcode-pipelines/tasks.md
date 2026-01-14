# Tasks: Transcoding & File Movement Pipelines

**Input**: Design documents from `/specs/006-transcode-pipelines/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, research.md, quickstart.md

**Tests**: Not explicitly requested - tests OMITTED from task list.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## User Story Mapping

| Story | Priority | Title | Key Components |
|-------|----------|-------|----------------|
| US1 | P1 | Transcode Video with Quality Policy | TranscodePolicyConfig, PolicySchema extension, TranscodeExecutor |
| US2 | P1 | Job Queue for Long-Running Tasks | Job model, jobs table, CLI commands, Worker |
| US3 | P2 | Audio Track Preservation Rules | AudioPreservationRule, audio codec handling |
| US4 | P2 | Directory Organization Policies | ParsedMetadata, DestinationTemplate, MoveExecutor |
| US5 | P2 | Safety and Rollback Options | Backup system, cleanup command, temp files |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and module structure

- [x] T001 Create jobs module directory structure in `src/vpo/jobs/__init__.py`
- [x] T002 [P] Create metadata module directory structure in `src/vpo/metadata/__init__.py`
- [x] T003 [P] Create test fixtures directory in `tests/fixtures/transcode/`

**Commit Checkpoint**: Commit all Phase 1 changes with message "feat(transcode): add module structure for jobs and metadata"

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data model extensions that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Add JobType and JobStatus enums in `src/vpo/db/models.py`
- [x] T005 [P] Add Job dataclass with all fields in `src/vpo/db/models.py`
- [x] T006 [P] Add JobProgress dataclass in `src/vpo/db/models.py`
- [x] T007 Create jobs table SQL schema (v5) in `src/vpo/db/schema.py`
- [x] T008 Implement migrate_v4_to_v5() migration in `src/vpo/db/schema.py`
- [x] T009 Update initialize_database() to call v4→v5 migration in `src/vpo/db/schema.py`
- [x] T010 [P] Add job CRUD operations (insert_job, get_job, update_job_status) in `src/vpo/db/models.py`
- [x] T011 [P] Add job query operations (get_queued_jobs, get_jobs_by_status) in `src/vpo/db/models.py`
- [x] T012 Extend config models with jobs/worker settings in `src/vpo/config/models.py`
- [x] T013 Update config loader to parse jobs/worker settings in `src/vpo/config/loader.py`

**Commit Checkpoint**: Commit all Phase 2 changes with message "feat(transcode): add Job model, schema v5, and config extensions"

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Transcode Video with Quality Policy (Priority: P1) MVP

**Goal**: Users can define transcoding settings (codec, CRF, resolution) in policy YAML and transcode video files

**Independent Test**: Define a policy with `target_video_codec: hevc` and `target_crf: 20`, run transcode on H.264 file, verify output is H.265

### Implementation for User Story 1

- [x] T014 [P] [US1] Add TranscodePolicyConfig dataclass in `src/vpo/policy/models.py`
- [x] T015 [P] [US1] Add validation for TranscodePolicyConfig (CRF 0-51, valid codecs) in `src/vpo/policy/models.py`
- [x] T016 [US1] Extend PolicySchema to include optional transcode field in `src/vpo/policy/models.py`
- [x] T017 [US1] Update policy loader to parse transcode section in `src/vpo/policy/loader.py`
- [x] T018 [P] [US1] Create FFmpeg progress parser in `src/vpo/jobs/progress.py`
- [x] T019 [US1] Create TranscodeExecutor with FFmpeg subprocess in `src/vpo/executor/transcode.py`
- [x] T020 [US1] Implement codec compliance check (skip if already compliant) in `src/vpo/executor/transcode.py`
- [x] T021 [US1] Implement resolution scaling logic in TranscodeExecutor in `src/vpo/executor/transcode.py`
- [x] T022 [US1] Implement dry-run mode for TranscodeExecutor in `src/vpo/executor/transcode.py`
- [x] T023 [US1] Create transcode CLI command in `src/vpo/cli/transcode.py`
- [x] T024 [US1] Implement --policy, --codec, --crf, --max-resolution options in `src/vpo/cli/transcode.py`
- [x] T025 [US1] Implement --dry-run and --recursive options in `src/vpo/cli/transcode.py`
- [x] T026 [US1] Register transcode command in CLI main in `src/vpo/cli/__init__.py`

**Commit Checkpoint**: Commit all US1 changes with message "feat(transcode): implement video transcoding with quality policy (US1)"

**Checkpoint**: User Story 1 complete - video transcoding works with policy settings

---

## Phase 4: User Story 2 - Job Queue for Long-Running Tasks (Priority: P1)

**Goal**: Users can queue transcode jobs and process them via `vpo jobs start` worker with limits

**Independent Test**: Submit multiple transcode jobs, run `vpo jobs start --max-files 2`, verify 2 jobs processed and queue shows remaining

### Implementation for User Story 2

- [x] T027 [P] [US2] Implement job queue operations (enqueue, claim_next, release) in `src/vpo/jobs/queue.py`
- [x] T028 [P] [US2] Implement atomic job claim with BEGIN IMMEDIATE in `src/vpo/jobs/queue.py`
- [x] T029 [US2] Implement stale job recovery (reset orphaned RUNNING to QUEUED) in `src/vpo/jobs/queue.py`
- [x] T030 [US2] Create JobWorker class in `src/vpo/jobs/worker.py`
- [x] T031 [US2] Implement worker limit checks (max_files, max_duration, end_by) in `src/vpo/jobs/worker.py`
- [x] T032 [US2] Implement worker heartbeat updates in `src/vpo/jobs/worker.py`
- [x] T033 [US2] Implement graceful shutdown on SIGTERM/SIGINT in `src/vpo/jobs/worker.py`
- [x] T034 [US2] Implement job progress updates during transcoding in `src/vpo/jobs/worker.py`
- [x] T035 [US2] Implement auto-purge of old jobs on worker startup in `src/vpo/jobs/worker.py`
- [x] T036 [US2] Create jobs CLI command group in `src/vpo/cli/jobs.py`
- [x] T037 [US2] Implement `vpo jobs list` command in `src/vpo/cli/jobs.py`
- [x] T038 [US2] Implement `vpo jobs status <job-id>` command in `src/vpo/cli/jobs.py`
- [x] T039 [US2] Implement `vpo jobs start` command with limit options in `src/vpo/cli/jobs.py`
- [x] T040 [US2] Implement `vpo jobs cancel <job-id>` command in `src/vpo/cli/jobs.py`
- [x] T041 [US2] Register jobs command group in CLI main in `src/vpo/cli/__init__.py`
- [x] T042 [US2] Update transcode CLI to queue jobs instead of executing directly in `src/vpo/cli/transcode.py`

**Commit Checkpoint**: Commit all US2 changes with message "feat(transcode): implement job queue and worker system (US2)"

**Checkpoint**: User Story 2 complete - job queue system functional with CLI

---

## Phase 5: User Story 3 - Audio Track Preservation Rules (Priority: P2)

**Goal**: Users can specify which audio codecs to preserve vs transcode in policy

**Independent Test**: Create policy with `audio_preserve_codecs: [truehd]`, process file with TrueHD and AC3, verify TrueHD copied and AC3 transcoded to AAC

### Implementation for User Story 3

- [x] T043 [P] [US3] Add AudioPreservationRule dataclass in `src/vpo/policy/models.py`
- [x] T044 [US3] Add audio preservation fields to TranscodePolicyConfig in `src/vpo/policy/models.py`
- [x] T045 [US3] Implement audio codec matching logic in `src/vpo/policy/transcode.py`
- [x] T046 [US3] Implement per-track audio handling in TranscodeExecutor in `src/vpo/executor/transcode.py`
- [x] T047 [US3] Implement audio stream copy for preserved codecs in `src/vpo/executor/transcode.py`
- [x] T048 [US3] Implement audio transcoding to target codec in `src/vpo/executor/transcode.py`
- [x] T049 [US3] Implement audio downmix option (stereo track creation) in `src/vpo/executor/transcode.py`
- [x] T050 [US3] Update dry-run to show audio handling plan in `src/vpo/executor/transcode.py`

**Commit Checkpoint**: Commit all US3 changes with message "feat(transcode): implement audio track preservation rules (US3)"

**Checkpoint**: User Story 3 complete - audio preservation works per policy

---

## Phase 6: User Story 4 - Directory Organization Policies (Priority: P2)

**Goal**: Users can define destination templates with metadata placeholders for automatic file organization

**Independent Test**: Create policy with `destination: "Movies/{year}/{title}"`, process file "Movie.Name.2023.mkv", verify output in `Movies/2023/Movie Name/`

### Implementation for User Story 4

- [x] T051 [P] [US4] Add ParsedMetadata dataclass in `src/vpo/metadata/parser.py`
- [x] T052 [P] [US4] Add DestinationTemplate dataclass in `src/vpo/metadata/templates.py`
- [x] T053 [US4] Implement filename parsing regex patterns (movie, TV) in `src/vpo/metadata/parser.py`
- [x] T054 [US4] Implement parse_filename() function in `src/vpo/metadata/parser.py`
- [x] T055 [US4] Implement template placeholder extraction in `src/vpo/metadata/templates.py`
- [x] T056 [US4] Implement template render() with fallback values in `src/vpo/metadata/templates.py`
- [x] T057 [US4] Create MoveExecutor for file movement in `src/vpo/executor/move.py`
- [x] T058 [US4] Implement directory creation in MoveExecutor in `src/vpo/executor/move.py`
- [x] T059 [US4] Add destination field handling to TranscodePolicyConfig in `src/vpo/policy/models.py`
- [x] T060 [US4] Integrate file movement after transcode completion in `src/vpo/jobs/worker.py`
- [x] T061 [US4] Update dry-run to show destination path in `src/vpo/cli/transcode.py`
- [x] T062 [P] [US4] Add MetadataExtractedEvent for plugin hook in `src/vpo/plugin/events.py`

**Commit Checkpoint**: Commit all US4 changes with message "feat(transcode): implement directory organization policies (US4)"

**Checkpoint**: User Story 4 complete - file organization works with metadata templates

---

## Phase 7: User Story 5 - Safety and Rollback Options (Priority: P2)

**Goal**: Users can configure backup/temp options to recover from failed operations

**Independent Test**: Enable `backup_original: true`, run transcode, verify original renamed to `.original`; simulate failure, verify original preserved

### Implementation for User Story 5

- [x] T063 [P] [US5] Add backup_original and temp_directory to config models in `src/vpo/config/models.py`
- [x] T064 [US5] Implement write-to-temp-then-move pattern in TranscodeExecutor in `src/vpo/executor/transcode.py`
- [x] T065 [US5] Implement original file backup on success in `src/vpo/executor/transcode.py`
- [x] T066 [US5] Implement partial output cleanup on failure in `src/vpo/executor/transcode.py`
- [x] T067 [US5] Implement disk space pre-check before transcoding in `src/vpo/executor/transcode.py`
- [x] T068 [US5] Add detailed operation logging for rollback info in `src/vpo/jobs/worker.py`
- [x] T069 [US5] Implement `vpo jobs cleanup` command in `src/vpo/cli/jobs.py`
- [x] T070 [US5] Implement --older-than and --include-backups options for cleanup in `src/vpo/cli/jobs.py`
- [x] T071 [US5] Implement orphaned temp file cleanup in `src/vpo/cli/jobs.py`

**Commit Checkpoint**: Commit all US5 changes with message "feat(transcode): implement safety and rollback options (US5)"

**Checkpoint**: User Story 5 complete - safety features protect user data

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, and final refinements

- [x] T072 [P] Add transcode policy documentation in `docs/usage/transcode-policy.md`
- [x] T073 [P] Add job system documentation in `docs/usage/jobs.md`
- [x] T074 Update CLI help text for all new commands in `src/vpo/cli/`
- [x] T075 Add example transcode policy to `examples/policies/transcode-hevc.yaml`
- [x] T076 Validate quickstart.md scenarios work end-to-end
- [x] T077 Update README.md with transcode feature overview

**Commit Checkpoint**: Commit all Phase 8 changes with message "docs(transcode): add documentation and examples"

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) ──▶ Phase 2 (Foundational) ──┬──▶ Phase 3 (US1: Transcode)
                                              │
                                              ├──▶ Phase 4 (US2: Job Queue)
                                              │
                                              ├──▶ Phase 5 (US3: Audio)
                                              │
                                              ├──▶ Phase 6 (US4: Directory)
                                              │
                                              └──▶ Phase 7 (US5: Safety)
                                                          │
                                                          ▼
                                              Phase 8 (Polish)
```

### User Story Dependencies

| Story | Depends On | Can Start After |
|-------|------------|-----------------|
| US1 (Transcode) | Phase 2 | Phase 2 complete |
| US2 (Job Queue) | Phase 2 | Phase 2 complete |
| US3 (Audio) | US1 | US1 complete (extends TranscodeExecutor) |
| US4 (Directory) | US2 | US2 complete (integrates with worker) |
| US5 (Safety) | US1, US2 | US1+US2 complete (extends both) |

### Recommended Execution Order

For single developer:
1. Phase 1 → Phase 2 → US1 → US2 → US3 → US4 → US5 → Phase 8

For parallel development:
1. Phase 1 → Phase 2 (everyone)
2. Developer A: US1 → US3
3. Developer B: US2 → US4 → US5
4. Everyone: Phase 8

### Parallel Opportunities per Phase

**Phase 2 (Foundational)**:
```
T004, T005, T006 (enums and dataclasses - same file, sequential)
T007, T008, T009 (schema - sequential)
T010, T011 (job operations - parallel)
T012, T013 (config - sequential)
```

**Phase 3 (US1)**:
```
T014, T015 (TranscodePolicyConfig - parallel)
T018 (progress parser - parallel with above)
```

**Phase 4 (US2)**:
```
T027, T028, T029 (queue operations - sequential within file)
T036-T041 (CLI commands - parallel after T030-T035)
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 (Transcode) - **Basic transcoding works**
4. Complete Phase 4: US2 (Job Queue) - **MVP complete: queue + process**
5. **STOP and VALIDATE**: Submit job, run worker, verify output
6. Demo/deploy MVP

### Incremental Delivery

| Increment | Stories | Capability Added |
|-----------|---------|------------------|
| MVP | US1 + US2 | Basic transcode with job queue |
| +Audio | US3 | Preserve lossless, transcode lossy |
| +Organization | US4 | Auto-organize output files |
| +Safety | US5 | Backup, cleanup, rollback |

### Commit Strategy

Per user request, commit after each phase:
- Phase 1: `feat(transcode): add module structure for jobs and metadata`
- Phase 2: `feat(transcode): add Job model, schema v5, and config extensions`
- Phase 3: `feat(transcode): implement video transcoding with quality policy (US1)`
- Phase 4: `feat(transcode): implement job queue and worker system (US2)`
- Phase 5: `feat(transcode): implement audio track preservation rules (US3)`
- Phase 6: `feat(transcode): implement directory organization policies (US4)`
- Phase 7: `feat(transcode): implement safety and rollback options (US5)`
- Phase 8: `docs(transcode): add documentation and examples`

---

## Notes

- [P] tasks = different files, no dependencies within that phase
- [Story] label maps task to specific user story for traceability
- Each user story should be independently testable after completion
- Commit after each phase completion (per user request)
- Stop at any checkpoint to validate story independently
- FFmpeg must be available in PATH for transcoding to work
