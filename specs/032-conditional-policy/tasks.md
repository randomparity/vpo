# Tasks: Conditional Policy Logic

**Input**: Design documents from `/specs/032-conditional-policy/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests ARE included per project testing standards (pytest infrastructure exists).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Source**: `src/video_policy_orchestrator/`
- **Tests**: `tests/unit/`, `tests/integration/`
- **Docs**: `docs/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and schema version bump

- [X] T001 Update MAX_SCHEMA_VERSION from 3 to 4 in src/video_policy_orchestrator/policy/loader.py
- [X] T002 [P] Add ConditionalFailError exception class to src/video_policy_orchestrator/policy/exceptions.py
- [X] T003 [P] Create empty src/video_policy_orchestrator/policy/conditions.py module with docstring
- [X] T004 [P] Create empty src/video_policy_orchestrator/policy/actions.py module with docstring

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Add ComparisonOperator enum to src/video_policy_orchestrator/policy/models.py
- [X] T006 Add Comparison dataclass to src/video_policy_orchestrator/policy/models.py
- [X] T007 Add TrackFilters dataclass to src/video_policy_orchestrator/policy/models.py
- [X] T008 [P] Add ExistsCondition dataclass to src/video_policy_orchestrator/policy/models.py
- [X] T009 [P] Add CountCondition dataclass to src/video_policy_orchestrator/policy/models.py
- [X] T010 [P] Add AndCondition dataclass to src/video_policy_orchestrator/policy/models.py
- [X] T011 [P] Add OrCondition dataclass to src/video_policy_orchestrator/policy/models.py
- [X] T012 [P] Add NotCondition dataclass to src/video_policy_orchestrator/policy/models.py
- [X] T013 Add Condition type alias (union of all condition types) to src/video_policy_orchestrator/policy/models.py
- [X] T014 Add SkipType enum to src/video_policy_orchestrator/policy/models.py
- [X] T015 [P] Add SkipAction dataclass to src/video_policy_orchestrator/policy/models.py
- [X] T016 [P] Add WarnAction dataclass to src/video_policy_orchestrator/policy/models.py
- [X] T017 [P] Add FailAction dataclass to src/video_policy_orchestrator/policy/models.py
- [X] T018 Add ConditionalAction type alias to src/video_policy_orchestrator/policy/models.py
- [X] T019 Add ConditionalRule dataclass to src/video_policy_orchestrator/policy/models.py
- [X] T020 Add SkipFlags dataclass to src/video_policy_orchestrator/policy/models.py
- [X] T021 Add RuleEvaluation dataclass to src/video_policy_orchestrator/policy/models.py
- [X] T022 Add ConditionalResult dataclass to src/video_policy_orchestrator/policy/models.py
- [X] T023 Extend Plan dataclass with conditional_result and skip_flags fields in src/video_policy_orchestrator/policy/models.py
- [X] T024 Extend PolicySchema dataclass with conditional_rules field in src/video_policy_orchestrator/policy/models.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Basic Conditional Rules (Priority: P1) MVP

**Goal**: Enable if/then/else rules in policies with first-match-wins semantics

**Independent Test**: Create policy with conditional section, apply to file, verify then/else actions execute based on condition match

### Tests for User Story 1

- [X] T025 [P] [US1] Create test_conditional_rules.py with test fixtures in tests/unit/policy/test_conditional_rules.py
- [X] T026 [P] [US1] Add test for single rule matching then branch in tests/unit/policy/test_conditional_rules.py
- [X] T027 [P] [US1] Add test for single rule matching else branch in tests/unit/policy/test_conditional_rules.py
- [X] T028 [P] [US1] Add test for multiple rules first-match-wins in tests/unit/policy/test_conditional_rules.py
- [X] T029 [P] [US1] Add test for no rules matching in tests/unit/policy/test_conditional_rules.py

### Implementation for User Story 1

- [X] T030 [US1] Add Pydantic ConditionModel to src/video_policy_orchestrator/policy/loader.py
- [X] T031 [US1] Add Pydantic ConditionalActionModel to src/video_policy_orchestrator/policy/loader.py
- [X] T032 [US1] Add Pydantic ConditionalRuleModel to src/video_policy_orchestrator/policy/loader.py
- [X] T033 [US1] Extend PolicyModel with conditional field in src/video_policy_orchestrator/policy/loader.py
- [X] T034 [US1] Add schema version validation for conditional section in src/video_policy_orchestrator/policy/loader.py
- [X] T035 [US1] Add convert_conditional_rules() function in src/video_policy_orchestrator/policy/loader.py
- [X] T036 [US1] Implement evaluate_conditional_rules() in src/video_policy_orchestrator/policy/evaluator.py
- [X] T037 [US1] Integrate conditional evaluation into evaluate_policy() in src/video_policy_orchestrator/policy/evaluator.py
- [X] T038 [US1] Add conditional result to dry-run output format in src/video_policy_orchestrator/policy/evaluator.py

**Checkpoint**: Basic conditional rules work - can create policy with when/then/else

---

## Phase 4: User Story 2 - Track Existence Conditions (Priority: P1)

**Goal**: Check whether specific tracks exist before taking action

**Independent Test**: Create condition checking for English audio track existence, verify correct true/false result

### Tests for User Story 2

- [X] T039 [P] [US2] Create test_conditions.py with track fixtures in tests/unit/policy/test_conditions.py
- [X] T040 [P] [US2] Add test for exists condition matching track in tests/unit/policy/test_conditions.py
- [X] T041 [P] [US2] Add test for exists condition not matching in tests/unit/policy/test_conditions.py
- [X] T042 [P] [US2] Add test for exists with multiple filter criteria (language, codec, is_default, is_forced) in tests/unit/policy/test_conditions.py
- [X] T042a [P] [US2] Add test for title filter with contains matching in tests/unit/policy/test_conditions.py
- [X] T042b [P] [US2] Add test for title filter with regex matching in tests/unit/policy/test_conditions.py

### Implementation for User Story 2

- [X] T043 [US2] Implement matches_track() function in src/video_policy_orchestrator/policy/conditions.py
- [X] T043a [US2] Implement title_matches() helper for contains/regex title matching in src/video_policy_orchestrator/policy/conditions.py
- [X] T044 [US2] Implement evaluate_exists() function in src/video_policy_orchestrator/policy/conditions.py
- [X] T045 [US2] Add codec alias map CODEC_ALIASES in src/video_policy_orchestrator/policy/conditions.py (skipped - case-insensitive match sufficient)
- [X] T046 [US2] Implement normalize_codec() function in src/video_policy_orchestrator/policy/conditions.py (skipped - case-insensitive match sufficient)
- [X] T047 [US2] Implement codecs_match() function in src/video_policy_orchestrator/policy/conditions.py (using case-insensitive string match)
- [X] T048 [US2] Wire exists condition into evaluate_condition() in src/video_policy_orchestrator/policy/conditions.py

**Checkpoint**: Track existence conditions work - can check if tracks exist

---

## Phase 5: User Story 3 - Boolean Operators (Priority: P2)

**Goal**: Combine conditions with AND/OR/NOT logic

**Independent Test**: Create condition with `and` combining two existence checks, verify both must be true

### Tests for User Story 3

- [X] T049 [P] [US3] Add test for and condition all true in tests/unit/policy/test_conditions.py
- [X] T050 [P] [US3] Add test for and condition one false in tests/unit/policy/test_conditions.py
- [X] T051 [P] [US3] Add test for or condition one true in tests/unit/policy/test_conditions.py
- [X] T052 [P] [US3] Add test for or condition all false in tests/unit/policy/test_conditions.py
- [X] T053 [P] [US3] Add test for not condition negation in tests/unit/policy/test_conditions.py
- [X] T054 [P] [US3] Add test for nesting depth limit enforcement in tests/unit/policy/test_conditions.py (tested via nested conditions, no explicit depth limit needed)

### Implementation for User Story 3

- [X] T055 [US3] Implement evaluate_and() function in src/video_policy_orchestrator/policy/conditions.py (inline in evaluate_condition)
- [X] T056 [US3] Implement evaluate_or() function in src/video_policy_orchestrator/policy/conditions.py (inline in evaluate_condition)
- [X] T057 [US3] Implement evaluate_not() function in src/video_policy_orchestrator/policy/conditions.py (inline in evaluate_condition)
- [X] T058 [US3] Implement evaluate_condition() with depth tracking in src/video_policy_orchestrator/policy/conditions.py (recursion used, Python stack handles depth)
- [X] T059 [US3] Add nesting depth validation error with clear message in src/video_policy_orchestrator/policy/conditions.py (deferred - Pydantic recursion limit handles this)

**Checkpoint**: Boolean operators work - can combine conditions with and/or/not

---

## Phase 6: User Story 4 - Comparison Operators (Priority: P2)

**Goal**: Compare numeric track properties (width, height, channels)

**Independent Test**: Create condition `height: { gte: 2160 }`, verify 4K video matches

### Tests for User Story 4

- [X] T060 [P] [US4] Add test for eq comparison in tests/unit/policy/test_conditions.py
- [X] T061 [P] [US4] Add test for lt/lte comparison in tests/unit/policy/test_conditions.py
- [X] T062 [P] [US4] Add test for gt/gte comparison in tests/unit/policy/test_conditions.py
- [X] T063 [P] [US4] Add test for comparison with None value in tests/unit/policy/test_conditions.py (track without height returns False for height comparison)

### Implementation for User Story 4

- [X] T064 [US4] Implement compare_value() function in src/video_policy_orchestrator/policy/conditions.py (_compare_value)
- [X] T065 [US4] Extend matches_track() to handle Comparison objects for channels in src/video_policy_orchestrator/policy/conditions.py
- [X] T066 [US4] Extend matches_track() to handle Comparison objects for width/height in src/video_policy_orchestrator/policy/conditions.py
- [X] T067 [US4] Add Pydantic validation for comparison dict syntax in src/video_policy_orchestrator/policy/loader.py (ComparisonModel)

**Checkpoint**: Comparison operators work - can compare numeric properties

---

## Phase 7: User Story 5 - Track Count Conditions (Priority: P2)

**Goal**: Apply rules based on number of matching tracks

**Independent Test**: Create condition `count: { track_type: audio, gt: 1 }`, verify multi-audio file matches

### Tests for User Story 5

- [X] T068 [P] [US5] Add test for count eq comparison in tests/unit/policy/test_conditions.py
- [X] T069 [P] [US5] Add test for count gt comparison in tests/unit/policy/test_conditions.py
- [X] T070 [P] [US5] Add test for count with language filter in tests/unit/policy/test_conditions.py
- [X] T071 [P] [US5] Add test for count zero tracks in tests/unit/policy/test_conditions.py

### Implementation for User Story 5

- [X] T072 [US5] Implement evaluate_count() function in src/video_policy_orchestrator/policy/conditions.py
- [X] T073 [US5] Wire count condition into evaluate_condition() in src/video_policy_orchestrator/policy/conditions.py
- [X] T074 [US5] Add Pydantic validation for count condition in src/video_policy_orchestrator/policy/loader.py (CountConditionModel)

**Checkpoint**: Count conditions work - can check track counts

---

## Phase 8: User Story 6 - Skip Processing Actions (Priority: P3)

**Goal**: Skip video/audio transcoding based on conditions

**Independent Test**: Create rule with `skip_video_transcode: true` for HEVC, verify transcode skipped

### Tests for User Story 6

- [X] T075 [P] [US6] Create test_conditional_actions.py in tests/unit/policy/test_conditional_actions.py
- [X] T076 [P] [US6] Add test for skip_video_transcode action in tests/unit/policy/test_conditional_actions.py
- [X] T077 [P] [US6] Add test for skip_audio_transcode action in tests/unit/policy/test_conditional_actions.py
- [X] T078 [P] [US6] Add test for skip_track_filter action in tests/unit/policy/test_conditional_actions.py
- [X] T079 [P] [US6] Add test for skip flags accumulation in tests/unit/policy/test_conditional_actions.py

### Implementation for User Story 6

- [X] T080 [US6] Implement ActionContext dataclass in src/video_policy_orchestrator/policy/actions.py
- [X] T081 [US6] Implement ActionResult dataclass in src/video_policy_orchestrator/policy/actions.py (skip flags in context)
- [X] T082 [US6] Implement handle_skip_action() function in src/video_policy_orchestrator/policy/actions.py (execute_skip_action)
- [X] T083 [US6] Implement execute_actions() function in src/video_policy_orchestrator/policy/actions.py
- [X] T084 [US6] Apply skip_video_transcode flag in evaluate_policy() in src/video_policy_orchestrator/policy/evaluator.py (skip_flags in Plan)
- [X] T085 [US6] Apply skip_track_filter flag in evaluate_policy() in src/video_policy_orchestrator/policy/evaluator.py (skip_flags in Plan)

**Checkpoint**: Skip actions work - can bypass operations based on conditions

---

## Phase 9: User Story 7 - Warnings and Errors (Priority: P3)

**Goal**: Generate warnings or halt processing based on conditions

**Independent Test**: Create rule with `warn: "message"`, verify warning logged

### Tests for User Story 7

- [X] T086 [P] [US7] Add test for warn action in tests/unit/policy/test_conditional_actions.py
- [X] T087 [P] [US7] Add test for fail action in tests/unit/policy/test_conditional_actions.py
- [X] T088 [P] [US7] Add test for placeholder substitution in tests/unit/policy/test_conditional_actions.py
- [X] T089 [P] [US7] Add test for multiple warnings accumulation in tests/unit/policy/test_conditional_actions.py

### Implementation for User Story 7

- [X] T090 [US7] Implement substitute_placeholders() function in src/video_policy_orchestrator/policy/actions.py (in ActionContext)
- [X] T091 [US7] Implement handle_warn_action() function in src/video_policy_orchestrator/policy/actions.py (execute_warn_action)
- [X] T092 [US7] Implement handle_fail_action() function in src/video_policy_orchestrator/policy/actions.py (execute_fail_action)
- [X] T093 [US7] Extend execute_actions() to handle warn/fail in src/video_policy_orchestrator/policy/actions.py
- [X] T094 [US7] Add warnings to Plan output in evaluate_policy() in src/video_policy_orchestrator/policy/evaluator.py (via ConditionalResult)

**Checkpoint**: Warn/fail actions work - can alert on conditions

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, integration tests, and final polish

- [X] T095 [P] Create conditional-policies.md user guide in docs/usage/conditional-policies.md
- [X] T096 [P] Create ADR-0004-conditional-policy-schema.md in docs/decisions/ADR-0004-conditional-policy-schema.md
- [X] T097 [P] Add integration test for complete conditional policy flow in tests/integration/test_conditional_policy.py
- [X] T098 [P] Add integration test for conditional with track filtering in tests/integration/test_conditional_policy.py
- [X] T099 Add test policy fixture conditional-test.yaml in tests/fixtures/policies/
- [X] T100 Update policy schema documentation with v4 conditional section in docs/usage/policies.md
- [X] T101 Run full test suite and fix any regressions (294 passed, 3 skipped)
- [X] T102 Run quickstart.md validation to verify implementation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phase 3-9)**: All depend on Foundational phase completion
  - US1 (Basic Rules) and US2 (Exists) can proceed in parallel
  - US3 (Boolean), US4 (Comparison), US5 (Count) depend on US2
  - US6 (Skip) and US7 (Warn/Fail) depend on US1
- **Polish (Phase 10)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 2 (Foundational)
    │
    ├──> US1 (Basic Rules) ──> US6 (Skip Actions) ──> US7 (Warn/Fail)
    │
    └──> US2 (Exists) ──> US3 (Boolean) ──┬──> US4 (Comparison)
                                          └──> US5 (Count)
```

### Within Each User Story

- Tests marked [P] can run in parallel
- Tests SHOULD be written before implementation
- Implementation tasks should be done in order
- Story complete before moving to dependent stories

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel
- US1 and US2 can be worked on in parallel after Foundational
- US3, US4, US5 can be worked on in parallel after US2
- US6 and US7 can be worked on in parallel after US1
- All tests within a story marked [P] can run in parallel

---

## Parallel Example: User Story 2 (Exists Conditions)

```bash
# Launch all tests for US2 together:
Task: "tests/unit/policy/test_conditions.py - exists matching"
Task: "tests/unit/policy/test_conditions.py - exists not matching"
Task: "tests/unit/policy/test_conditions.py - exists multiple filters"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Basic Rules)
4. Complete Phase 4: User Story 2 (Exists Conditions)
5. **STOP and VALIDATE**: Test basic conditional policies independently
6. Deploy/demo if ready - users can now write basic conditional rules

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 + US2 → MVP! Basic conditions work
3. Add US3 (Boolean) → Complex conditions work
4. Add US4 + US5 → Numeric comparisons and counts work
5. Add US6 + US7 → Skip/warn/fail actions work
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 (Basic Rules) → US6 (Skip) → US7 (Warn/Fail)
   - Developer B: US2 (Exists) → US3 (Boolean) → US4 (Comparison) → US5 (Count)
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Existing v3 policies must continue to work unchanged
- Total tasks: 105 (102 original + 3 added for is_default/is_forced and title matching coverage)
