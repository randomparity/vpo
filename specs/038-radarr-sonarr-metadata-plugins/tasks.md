# Tasks: Radarr and Sonarr Metadata Plugins

**Input**: Design documents from `/specs/038-radarr-sonarr-metadata-plugins/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not explicitly requested in the feature specification. Tests are omitted.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## User Story Mapping

| Story | Title | Priority |
|-------|-------|----------|
| US1 | Configure Radarr Connection | P1 |
| US2 | Configure Sonarr Connection | P1 |
| US3 | Enrich Movie Metadata from Radarr | P2 |
| US4 | Enrich TV Series Metadata from Sonarr | P2 |
| US5 | Apply Original Language to Video Tracks | P3 |
| US6 | View Enriched Metadata in UI | P3 |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create plugin package structure and shared configuration models

- [X] T001 [P] Create Radarr plugin package directory at src/video_policy_orchestrator/plugins/radarr_metadata/__init__.py
- [X] T002 [P] Create Sonarr plugin package directory at src/video_policy_orchestrator/plugins/sonarr_metadata/__init__.py
- [X] T003 Add PluginConnectionConfig dataclass to src/video_policy_orchestrator/config/models.py
- [X] T004 Add MetadataPluginSettings dataclass to src/video_policy_orchestrator/config/models.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models and utilities that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Create RadarrLanguage dataclass in src/video_policy_orchestrator/plugins/radarr_metadata/models.py
- [X] T006 Create RadarrMovie dataclass in src/video_policy_orchestrator/plugins/radarr_metadata/models.py
- [X] T007 Create RadarrMovieFile dataclass in src/video_policy_orchestrator/plugins/radarr_metadata/models.py
- [X] T008 Create RadarrCache dataclass with lookup_by_path method in src/video_policy_orchestrator/plugins/radarr_metadata/models.py
- [X] T009 [P] Create SonarrLanguage dataclass in src/video_policy_orchestrator/plugins/sonarr_metadata/models.py
- [X] T010 [P] Create SonarrSeries dataclass in src/video_policy_orchestrator/plugins/sonarr_metadata/models.py
- [X] T011 [P] Create SonarrEpisode dataclass in src/video_policy_orchestrator/plugins/sonarr_metadata/models.py
- [X] T012 [P] Create SonarrParseResult dataclass in src/video_policy_orchestrator/plugins/sonarr_metadata/models.py
- [X] T013 [P] Create SonarrCache dataclass with lookup_by_path method in src/video_policy_orchestrator/plugins/sonarr_metadata/models.py
- [X] T014 Create MatchStatus enum in src/video_policy_orchestrator/plugins/radarr_metadata/models.py
- [X] T015 Create MatchResult dataclass in src/video_policy_orchestrator/plugins/radarr_metadata/models.py
- [X] T016 Create MetadataEnrichment dataclass with to_dict method in src/video_policy_orchestrator/plugins/radarr_metadata/models.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Configure Radarr Connection (Priority: P1)

**Goal**: Users can configure VPO to connect to their Radarr instance with URL and API key validation

**Independent Test**: Configure a Radarr connection and receive confirmation of successful authentication

### Implementation for User Story 1

- [X] T017 [US1] Implement RadarrClient class with __init__ accepting PluginConnectionConfig in src/video_policy_orchestrator/plugins/radarr_metadata/client.py
- [X] T018 [US1] Implement _headers method returning X-Api-Key header in src/video_policy_orchestrator/plugins/radarr_metadata/client.py
- [X] T019 [US1] Implement get_status method calling GET /api/v3/system/status in src/video_policy_orchestrator/plugins/radarr_metadata/client.py
- [X] T020 [US1] Implement validate_connection method with timeout and error handling in src/video_policy_orchestrator/plugins/radarr_metadata/client.py
- [X] T021 [US1] Add connection validation error messages for invalid API key (401) and unreachable URL in src/video_policy_orchestrator/plugins/radarr_metadata/client.py
- [X] T022 [US1] Create RadarrMetadataPlugin class with name, version, events attributes in src/video_policy_orchestrator/plugins/radarr_metadata/plugin.py
- [X] T023 [US1] Implement plugin __init__ that validates connection on startup in src/video_policy_orchestrator/plugins/radarr_metadata/plugin.py
- [X] T024 [US1] Add structured logging for connection success/failure in src/video_policy_orchestrator/plugins/radarr_metadata/plugin.py

**Checkpoint**: Radarr connection configuration is functional and testable independently

---

## Phase 4: User Story 2 - Configure Sonarr Connection (Priority: P1)

**Goal**: Users can configure VPO to connect to their Sonarr instance with URL and API key validation

**Independent Test**: Configure a Sonarr connection and receive confirmation of successful authentication

### Implementation for User Story 2

- [X] T025 [US2] Implement SonarrClient class with __init__ accepting PluginConnectionConfig in src/video_policy_orchestrator/plugins/sonarr_metadata/client.py
- [X] T026 [US2] Implement _headers method returning X-Api-Key header in src/video_policy_orchestrator/plugins/sonarr_metadata/client.py
- [X] T027 [US2] Implement get_status method calling GET /api/v3/system/status in src/video_policy_orchestrator/plugins/sonarr_metadata/client.py
- [X] T028 [US2] Implement validate_connection method with timeout and error handling in src/video_policy_orchestrator/plugins/sonarr_metadata/client.py
- [X] T029 [US2] Add connection validation error messages for invalid API key (401) and unreachable URL in src/video_policy_orchestrator/plugins/sonarr_metadata/client.py
- [X] T030 [US2] Create SonarrMetadataPlugin class with name, version, events attributes in src/video_policy_orchestrator/plugins/sonarr_metadata/plugin.py
- [X] T031 [US2] Implement plugin __init__ that validates connection on startup in src/video_policy_orchestrator/plugins/sonarr_metadata/plugin.py
- [X] T032 [US2] Add structured logging for connection success/failure in src/video_policy_orchestrator/plugins/sonarr_metadata/plugin.py

**Checkpoint**: Sonarr connection configuration is functional and testable independently

---

## Phase 5: User Story 3 - Enrich Movie Metadata from Radarr (Priority: P2)

**Goal**: Scanned movie files are enriched with original language, title, and year from Radarr

**Independent Test**: Scan a movie file that exists in Radarr and verify metadata fields are populated

### Implementation for User Story 3

- [ ] T033 [US3] Implement get_movies method calling GET /api/v3/movie in src/video_policy_orchestrator/plugins/radarr_metadata/client.py
- [ ] T034 [US3] Implement get_movie_files method calling GET /api/v3/moviefile in src/video_policy_orchestrator/plugins/radarr_metadata/client.py
- [ ] T035 [US3] Implement _parse_movie_response to convert JSON to RadarrMovie in src/video_policy_orchestrator/plugins/radarr_metadata/client.py
- [ ] T036 [US3] Implement _parse_movie_file_response to convert JSON to RadarrMovieFile in src/video_policy_orchestrator/plugins/radarr_metadata/client.py
- [ ] T037 [US3] Implement build_cache method that fetches all movies and files and builds path index in src/video_policy_orchestrator/plugins/radarr_metadata/client.py
- [ ] T038 [US3] Add path normalization helper for consistent path matching in src/video_policy_orchestrator/plugins/radarr_metadata/client.py
- [ ] T039 [US3] Implement on_file_scanned event handler in src/video_policy_orchestrator/plugins/radarr_metadata/plugin.py
- [ ] T040 [US3] Implement cache initialization on first file scanned in src/video_policy_orchestrator/plugins/radarr_metadata/plugin.py
- [ ] T041 [US3] Implement _create_enrichment method using normalize_language in src/video_policy_orchestrator/plugins/radarr_metadata/plugin.py
- [ ] T042 [US3] Add error handling for API failures (graceful degradation) in src/video_policy_orchestrator/plugins/radarr_metadata/plugin.py
- [ ] T043 [US3] Add structured logging for match success, no match, and errors in src/video_policy_orchestrator/plugins/radarr_metadata/plugin.py

**Checkpoint**: Movie files are enriched with Radarr metadata during scans

---

## Phase 6: User Story 4 - Enrich TV Series Metadata from Sonarr (Priority: P2)

**Goal**: Scanned TV episode files are enriched with original language, series title, and season/episode from Sonarr

**Independent Test**: Scan a TV episode file that exists in Sonarr and verify metadata fields are populated

### Implementation for User Story 4

- [ ] T044 [US4] Implement parse method calling GET /api/v3/parse?path= in src/video_policy_orchestrator/plugins/sonarr_metadata/client.py
- [ ] T045 [US4] Implement _parse_series_response to convert JSON to SonarrSeries in src/video_policy_orchestrator/plugins/sonarr_metadata/client.py
- [ ] T046 [US4] Implement _parse_episode_response to convert JSON to SonarrEpisode in src/video_policy_orchestrator/plugins/sonarr_metadata/client.py
- [ ] T047 [US4] Implement _parse_parse_result to convert full parse response to SonarrParseResult in src/video_policy_orchestrator/plugins/sonarr_metadata/client.py
- [ ] T048 [US4] Add path normalization helper for consistent path matching in src/video_policy_orchestrator/plugins/sonarr_metadata/client.py
- [ ] T049 [US4] Implement on_file_scanned event handler in src/video_policy_orchestrator/plugins/sonarr_metadata/plugin.py
- [ ] T050 [US4] Implement lazy cache population using parse endpoint in src/video_policy_orchestrator/plugins/sonarr_metadata/plugin.py
- [ ] T051 [US4] Implement _create_enrichment method using normalize_language with TV-specific fields in src/video_policy_orchestrator/plugins/sonarr_metadata/plugin.py
- [ ] T052 [US4] Add error handling for API failures (graceful degradation) in src/video_policy_orchestrator/plugins/sonarr_metadata/plugin.py
- [ ] T053 [US4] Add structured logging for match success, no match, and errors in src/video_policy_orchestrator/plugins/sonarr_metadata/plugin.py

**Checkpoint**: TV episode files are enriched with Sonarr metadata during scans

---

## Phase 7: User Story 5 - Apply Original Language to Video Tracks (Priority: P3)

**Goal**: Policies can use original_language from enriched metadata to tag video tracks

**Independent Test**: Create a policy using original_language condition, apply to enriched file, verify video track is tagged

### Implementation for User Story 5

- [ ] T054 [US5] Document policy condition syntax for original_language in specs/038-radarr-sonarr-metadata-plugins/quickstart.md
- [ ] T055 [US5] Add example policy YAML showing original_language usage in specs/038-radarr-sonarr-metadata-plugins/quickstart.md
- [ ] T056 [US5] Verify enriched metadata is accessible in policy evaluation context

**Checkpoint**: Policies can use enriched original_language metadata

---

## Phase 8: User Story 6 - View Enriched Metadata in UI (Priority: P3)

**Goal**: Users can see enriched metadata source and fields in the web UI file details view

**Independent Test**: View a file in the web UI that has been enriched and verify metadata source and fields are displayed

### Implementation for User Story 6

- [ ] T057 [US6] Add enriched metadata section to src/video_policy_orchestrator/server/ui/templates/file_detail.html
- [ ] T058 [US6] Display external_source (Radarr/Sonarr) badge in file detail template
- [ ] T059 [US6] Display original_language in file detail template
- [ ] T060 [US6] Display external_title and external_year in file detail template
- [ ] T061 [US6] Display TV-specific fields (series_title, season_number, episode_number) conditionally in file detail template
- [ ] T062 [US6] Handle case when no enrichment is present (show nothing extra)

**Checkpoint**: Web UI displays enriched metadata from external sources

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Finalization and documentation

- [ ] T063 [P] Export plugin classes from package __init__.py files
- [ ] T064 [P] Add plugin entry points to pyproject.toml for automatic discovery
- [ ] T065 Update plugin documentation with Radarr/Sonarr configuration examples
- [ ] T066 Run quickstart.md validation with sample configuration
- [ ] T067 Verify graceful degradation when services are unavailable

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational phase completion
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 3 (P2)**: Depends on US1 (Radarr connection required for enrichment)
- **User Story 4 (P2)**: Depends on US2 (Sonarr connection required for enrichment)
- **User Story 5 (P3)**: Depends on US3 or US4 (needs enriched metadata to test)
- **User Story 6 (P3)**: Depends on US3 or US4 (needs enriched metadata to display)

### Within Each User Story

- Models before client methods
- Client methods before plugin logic
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- T001, T002 can run in parallel (different plugin packages)
- T005-T016 can all run in parallel (different model files)
- US1 and US2 can run in parallel after Foundational (different plugins)
- US3 and US4 can run in parallel after their respective US1/US2 dependencies
- US5 and US6 can run in parallel after US3 or US4

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Launch all model tasks together:
Task: "Create RadarrLanguage dataclass in .../radarr_metadata/models.py"
Task: "Create RadarrMovie dataclass in .../radarr_metadata/models.py"
Task: "Create RadarrMovieFile dataclass in .../radarr_metadata/models.py"
Task: "Create RadarrCache dataclass in .../radarr_metadata/models.py"
Task: "Create SonarrLanguage dataclass in .../sonarr_metadata/models.py"
Task: "Create SonarrSeries dataclass in .../sonarr_metadata/models.py"
Task: "Create SonarrEpisode dataclass in .../sonarr_metadata/models.py"
Task: "Create SonarrParseResult dataclass in .../sonarr_metadata/models.py"
Task: "Create SonarrCache dataclass in .../sonarr_metadata/models.py"
```

## Parallel Example: US1 + US2 (After Foundational)

```bash
# Launch Radarr and Sonarr client implementation in parallel:
Developer A:
Task: "Implement RadarrClient class in .../radarr_metadata/client.py"
Task: "Create RadarrMetadataPlugin class in .../radarr_metadata/plugin.py"

Developer B:
Task: "Implement SonarrClient class in .../sonarr_metadata/client.py"
Task: "Create SonarrMetadataPlugin class in .../sonarr_metadata/plugin.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Radarr Connection)
4. Complete Phase 4: User Story 2 (Sonarr Connection)
5. **STOP and VALIDATE**: Test both connections independently
6. Deploy/demo if ready - users can now configure connections

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1 + US2 → Test connections → Deploy (MVP!)
3. Add US3 → Test movie enrichment → Deploy
4. Add US4 → Test TV enrichment → Deploy
5. Add US5 + US6 → Test policy + UI → Deploy (Complete Feature)

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 (Radarr Connection) → US3 (Radarr Enrichment)
   - Developer B: US2 (Sonarr Connection) → US4 (Sonarr Enrichment)
3. After US3/US4: Either developer handles US5 + US6

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Radarr and Sonarr plugins are symmetric - similar patterns, parallel development
