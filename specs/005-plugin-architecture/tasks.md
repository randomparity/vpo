# Tasks: Plugin Architecture & Extension Model

**Input**: Design documents from `/specs/005-plugin-architecture/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are included as this is a foundational system component requiring validation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, etc.)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and package structure for plugin system

- [X] T001 Create plugin package directory structure at src/video_policy_orchestrator/plugin/
- [X] T002 [P] Create plugin_sdk package directory at src/video_policy_orchestrator/plugin_sdk/
- [X] T003 [P] Create plugins package directory at src/video_policy_orchestrator/plugins/
- [X] T004 [P] Create test directories at tests/unit/plugin/, tests/integration/, tests/contract/
- [X] T005 [P] Create examples directory at examples/plugins/simple_reorder_plugin/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data model extensions that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Extend database schema with plugin_acknowledgments table in src/video_policy_orchestrator/db/schema.py
- [ ] T007 [P] Add PluginAcknowledgment model to src/video_policy_orchestrator/db/models.py
- [ ] T008 [P] Add DB operations for plugin acknowledgments in src/video_policy_orchestrator/db/operations.py
- [ ] T009 [P] Extend config models with plugin_dirs setting in src/video_policy_orchestrator/config/models.py
- [ ] T010 Add plugin directory configuration loading in src/video_policy_orchestrator/config/loader.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Plugin Interface Definition (Priority: P1) 🎯 MVP

**Goal**: Define stable AnalyzerPlugin and MutatorPlugin interfaces that plugin authors can implement

**Independent Test**: Create a minimal plugin conforming to each interface and verify it validates without errors

### Tests for User Story 1

- [ ] T011 [P] [US1] Contract test for AnalyzerPlugin protocol in tests/contract/test_plugin_contracts.py
- [ ] T012 [P] [US1] Contract test for MutatorPlugin protocol in tests/contract/test_plugin_contracts.py
- [ ] T013 [P] [US1] Unit test for APIVersion parsing and comparison in tests/unit/plugin/test_version.py

### Implementation for User Story 1

- [ ] T014 [P] [US1] Implement PluginType and PluginSource enums in src/video_policy_orchestrator/plugin/manifest.py
- [ ] T015 [P] [US1] Implement PluginManifest dataclass in src/video_policy_orchestrator/plugin/manifest.py
- [ ] T016 [P] [US1] Implement APIVersion class with semver parsing in src/video_policy_orchestrator/plugin/version.py
- [ ] T017 [US1] Define AnalyzerPlugin protocol in src/video_policy_orchestrator/plugin/interfaces.py
- [ ] T018 [US1] Define MutatorPlugin protocol in src/video_policy_orchestrator/plugin/interfaces.py
- [ ] T019 [US1] Implement plugin event types (FileScannedEvent, etc.) in src/video_policy_orchestrator/plugin/events.py
- [ ] T020 [US1] Add PLUGIN_API_VERSION constant and version compatibility check in src/video_policy_orchestrator/plugin/version.py
- [ ] T021 [US1] Create public exports in src/video_policy_orchestrator/plugin/__init__.py

**Checkpoint**: Plugin interfaces defined and testable - developers can implement plugins against the protocol

---

## Phase 4: User Story 2 - Plugin Discovery & Loading (Priority: P1)

**Goal**: Auto-discover plugins from directories and Python entry points; provide `vpo plugins list` command

**Independent Test**: Place a plugin in ~/.vpo/plugins/ and verify it appears in `vpo plugins list`

### Tests for User Story 2

- [ ] T022 [P] [US2] Unit test for directory discovery in tests/unit/plugin/test_loader.py
- [ ] T023 [P] [US2] Unit test for entry point discovery in tests/unit/plugin/test_loader.py
- [ ] T024 [P] [US2] Unit test for PluginRegistry operations in tests/unit/plugin/test_registry.py
- [ ] T025 [P] [US2] Integration test for plugin discovery E2E in tests/integration/test_plugin_discovery.py

### Implementation for User Story 2

- [ ] T026 [US2] Implement directory plugin scanner in src/video_policy_orchestrator/plugin/loader.py
- [ ] T027 [US2] Implement entry point plugin scanner in src/video_policy_orchestrator/plugin/loader.py
- [ ] T028 [US2] Implement plugin validation (interface checking) in src/video_policy_orchestrator/plugin/loader.py
- [ ] T029 [US2] Implement PluginRegistry class in src/video_policy_orchestrator/plugin/registry.py
- [ ] T030 [US2] Add plugin acknowledgment flow for directory plugins in src/video_policy_orchestrator/plugin/loader.py (includes: warning message, y/N prompt with N default, non-interactive mode rejection, store acknowledgment in DB)
- [ ] T031 [US2] Implement plugin hash calculation for acknowledgment in src/video_policy_orchestrator/plugin/loader.py
- [ ] T032 [US2] Add plugin conflict detection and warning in src/video_policy_orchestrator/plugin/registry.py
- [ ] T033 [US2] Implement graceful error handling for plugin load failures in src/video_policy_orchestrator/plugin/loader.py
- [ ] T034 [US2] Add structured logging for discovery/loading in src/video_policy_orchestrator/plugin/loader.py
- [ ] T035 [US2] Implement `vpo plugins` command group (list, enable, disable subcommands) in src/video_policy_orchestrator/cli/plugins.py
- [ ] T036 [US2] Add --force-load-plugins CLI flag to root command in src/video_policy_orchestrator/cli/__init__.py
- [ ] T037 [US2] Wire plugins CLI command into main CLI group in src/video_policy_orchestrator/cli/__init__.py

**Checkpoint**: Plugin discovery works E2E - users can install plugins and see them in `vpo plugins list`

---

## Phase 5: User Story 3 - Built-In Policy Plugin (Priority: P2)

**Goal**: Refactor policy engine as a first-party plugin to dogfood the system and provide reference implementation

**Independent Test**: Disable built-in policy plugin and verify `vpo apply --policy` reports no plugin available

### Tests for User Story 3

- [ ] T038 [P] [US3] Unit test for PolicyEnginePlugin in tests/unit/plugin/test_policy_plugin.py
- [ ] T039 [P] [US3] Integration test: policy engine as plugin passes existing policy tests in tests/integration/test_policy_plugin.py

### Implementation for User Story 3

- [ ] T040 [US3] Create PolicyEnginePlugin class in src/video_policy_orchestrator/plugins/policy_engine/plugin.py
- [ ] T041 [US3] Implement AnalyzerPlugin methods for policy evaluation in src/video_policy_orchestrator/plugins/policy_engine/plugin.py
- [ ] T042 [US3] Implement MutatorPlugin methods for plan execution in src/video_policy_orchestrator/plugins/policy_engine/plugin.py
- [ ] T043 [US3] Wire existing policy/evaluator.py logic into plugin in src/video_policy_orchestrator/plugins/policy_engine/plugin.py
- [ ] T044 [US3] Register policy engine as built-in plugin in src/video_policy_orchestrator/plugins/policy_engine/__init__.py
- [ ] T045 [US3] Update `vpo apply` to use plugin system in src/video_policy_orchestrator/cli/apply.py
- [ ] T046 [US3] Add enable/disable support for built-in plugin in src/video_policy_orchestrator/plugin/registry.py

**Checkpoint**: Policy engine works as a plugin - validates architecture, provides reference implementation

---

## Phase 6: User Story 4 - Plugin SDK Skeleton (Priority: P2)

**Goal**: Provide minimal SDK with base classes and utilities to reduce boilerplate for plugin authors

**Independent Test**: Create a new plugin using SDK base classes and verify it loads correctly

### Tests for User Story 4

- [ ] T047 [P] [US4] Unit test for BaseAnalyzerPlugin in tests/unit/plugin/test_sdk.py
- [ ] T048 [P] [US4] Unit test for BaseMutatorPlugin in tests/unit/plugin/test_sdk.py
- [ ] T049 [P] [US4] Unit test for SDK helpers in tests/unit/plugin/test_sdk.py

### Implementation for User Story 4

- [ ] T050 [P] [US4] Implement BaseAnalyzerPlugin class in src/video_policy_orchestrator/plugin_sdk/base.py
- [ ] T051 [P] [US4] Implement BaseMutatorPlugin class in src/video_policy_orchestrator/plugin_sdk/base.py
- [ ] T052 [US4] Implement SDK helper functions (get_logger, get_config) in src/video_policy_orchestrator/plugin_sdk/helpers.py
- [ ] T053 [US4] Implement test utilities (PluginTestCase, mock helpers) in src/video_policy_orchestrator/plugin_sdk/testing.py
- [ ] T054 [US4] Create public exports in src/video_policy_orchestrator/plugin_sdk/__init__.py
- [ ] T055 [US4] Create example plugin pyproject.toml in examples/plugins/simple_reorder_plugin/pyproject.toml
- [ ] T056 [US4] Create example plugin README.md in examples/plugins/simple_reorder_plugin/README.md
- [ ] T057 [US4] Implement example plugin in examples/plugins/simple_reorder_plugin/src/simple_reorder/__init__.py

**Checkpoint**: SDK complete - plugin authors can create plugins with minimal boilerplate

---

## Phase 7: User Story 5 - Spec & Versioning Contract (Priority: P3)

**Goal**: Document plugin API versioning and enforce version compatibility at load time

**Independent Test**: Create plugin with incompatible version range, verify it's blocked with clear error message

### Tests for User Story 5

- [ ] T058 [P] [US5] Unit test for version compatibility checking in tests/unit/plugin/test_version.py
- [ ] T059 [P] [US5] Integration test for incompatible plugin blocking in tests/integration/test_plugin_discovery.py

### Implementation for User Story 5

- [ ] T060 [US5] Implement version range validation in plugin loader in src/video_policy_orchestrator/plugin/loader.py
- [ ] T061 [US5] Add version mismatch error messages in src/video_policy_orchestrator/plugin/loader.py
- [ ] T062 [US5] Implement --force-load-plugins override behavior in src/video_policy_orchestrator/plugin/registry.py
- [ ] T063 [US5] Create plugin development documentation in docs/plugins.md

**Checkpoint**: Version contracts enforced - ecosystem stability ensured

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cleanup, and validation

- [ ] T064 [P] Add API version to docs/plugins.md with compatibility guidelines
- [ ] T065 [P] Add deprecation policy section to docs/plugins.md
- [ ] T066 Verify example plugin compiles and runs without modification
- [ ] T067 Run quickstart.md scenarios to validate developer experience
- [ ] T068 Code cleanup and docstring completion across plugin/ and plugin_sdk/
- [ ] T069 Verify all existing tests pass (policy engine refactor didn't break anything)
- [ ] T070 Performance validation: plugin discovery < 1 second for 50 plugins

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational - defines interfaces
- **US2 (Phase 4)**: Depends on US1 - needs interfaces to validate plugins
- **US3 (Phase 5)**: Depends on US2 - needs registry to register built-in plugin
- **US4 (Phase 6)**: Depends on US1 - needs interfaces to implement base classes
- **US5 (Phase 7)**: Depends on US2 - needs loader for version enforcement
- **Polish (Phase 8)**: Depends on all user stories

### User Story Dependencies

```
              ┌─────────────────────────────────────────┐
              │        Phase 2: Foundational            │
              │         (BLOCKS ALL STORIES)            │
              └───────────────┬─────────────────────────┘
                              │
              ┌───────────────▼───────────────┐
              │   US1: Interface Definition   │
              │        (P1 - MVP Core)        │
              └───────────────┬───────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
   │ US2: Discovery│   │ US4: SDK     │   │ US5: Version │
   │    (P1)       │   │   (P2)       │   │   (P3)       │
   └───────┬───────┘   └──────────────┘   └──────────────┘
           │
           ▼
   ┌──────────────┐
   │ US3: Policy  │
   │ Plugin (P2)  │
   └──────────────┘
```

### Parallel Opportunities

Within phases:
- **Setup**: T002, T003, T004, T005 can run in parallel with T001
- **Foundational**: T007, T008, T009 can run in parallel after T006
- **US1**: T011-T013 (tests), T014-T016 (models) can run in parallel
- **US2**: T022-T025 (tests) can run in parallel
- **US4**: T047-T049 (tests), T050-T051 (base classes) can run in parallel

Across stories (with team capacity):
- US4 (SDK) can start once US1 is complete (parallel with US2)
- US5 (Versioning) can start once US2 is complete (parallel with US3)

---

## Parallel Example: Phase 3 (User Story 1)

```bash
# Launch all tests in parallel:
Task: "Contract test for AnalyzerPlugin protocol in tests/contract/test_plugin_contracts.py"
Task: "Contract test for MutatorPlugin protocol in tests/contract/test_plugin_contracts.py"
Task: "Unit test for APIVersion parsing in tests/unit/plugin/test_version.py"

# Launch parallel model tasks:
Task: "Implement PluginType and PluginSource enums in src/video_policy_orchestrator/plugin/manifest.py"
Task: "Implement PluginManifest dataclass in src/video_policy_orchestrator/plugin/manifest.py"
Task: "Implement APIVersion class in src/video_policy_orchestrator/plugin/version.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: US1 - Interface Definition
4. Complete Phase 4: US2 - Discovery & Loading
5. **STOP and VALIDATE**: Users can install and list plugins
6. Deploy/demo MVP

### Incremental Delivery

1. MVP → Plugin interfaces + discovery working
2. Add US3 → Policy engine as plugin (validates architecture)
3. Add US4 → SDK for plugin authors (ecosystem enablement)
4. Add US5 → Version contracts (long-term stability)
5. Each addition is independently valuable

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story
- Each user story is independently testable
- Commit after each task or logical group
- Stop at any checkpoint to validate independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies
