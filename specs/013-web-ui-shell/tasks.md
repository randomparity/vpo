# Tasks: Web UI Shell with Global Navigation

**Input**: Design documents from `/specs/013-web-ui-shell/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: No explicit test tasks requested. Tests omitted per task generation rules.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**Commits**: Changes should be committed to the branch after each phase is completed.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Project type**: Web application extending existing daemon server
- **Server code**: `src/video_policy_orchestrator/server/`
- **UI module**: `src/video_policy_orchestrator/server/ui/`
- **Static files**: `src/video_policy_orchestrator/server/static/`
- **Templates**: `src/video_policy_orchestrator/server/ui/templates/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependencies, and directory structure

- [ ] T001 Add aiohttp-jinja2 and jinja2 dependencies to pyproject.toml
- [ ] T002 [P] Create UI module directory structure at src/video_policy_orchestrator/server/ui/
- [ ] T003 [P] Create static files directory structure at src/video_policy_orchestrator/server/static/
- [ ] T004 [P] Create templates directory structure at src/video_policy_orchestrator/server/ui/templates/
- [ ] T005 Create UI module __init__.py at src/video_policy_orchestrator/server/ui/__init__.py

**Checkpoint**: Directory structure ready, dependencies declared

**Commit**: After Phase 1 completion, commit with message "feat(013): Setup Web UI shell project structure and dependencies"

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models and route infrastructure that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Define NavigationItem, NavigationState, and TemplateContext dataclasses in src/video_policy_orchestrator/server/ui/models.py
- [ ] T007 Define NAVIGATION_ITEMS configuration constant in src/video_policy_orchestrator/server/ui/models.py
- [ ] T008 Create base.html template with shell layout (nav placeholder, content area) in src/video_policy_orchestrator/server/ui/templates/base.html
- [ ] T009 Setup Jinja2 environment and template loader in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T010 Register UI routes with existing app in src/video_policy_orchestrator/server/app.py
- [ ] T011 Configure static file serving for /static/ path in src/video_policy_orchestrator/server/app.py

**Checkpoint**: Foundation ready - base template renders, static files serve, Jinja2 configured

**Commit**: After Phase 2 completion, commit with message "feat(013): Add foundational UI infrastructure and base template"

---

## Phase 3: User Story 1 - Navigate Between Sections (Priority: P1)

**Goal**: Enable navigation between 5 sections (Jobs, Library, Transcriptions, Policies, Approvals) with persistent navigation bar

**Independent Test**: Load any section URL, verify navigation bar appears with all 5 links, click links to navigate between sections

### Implementation for User Story 1

- [ ] T012 [US1] Create navigation component in base.html template with sidebar containing all 5 section links in src/video_policy_orchestrator/server/ui/templates/base.html
- [ ] T013 [P] [US1] Create jobs.html section template with placeholder content in src/video_policy_orchestrator/server/ui/templates/sections/jobs.html
- [ ] T014 [P] [US1] Create library.html section template with placeholder content in src/video_policy_orchestrator/server/ui/templates/sections/library.html
- [ ] T015 [P] [US1] Create transcriptions.html section template with placeholder content in src/video_policy_orchestrator/server/ui/templates/sections/transcriptions.html
- [ ] T016 [P] [US1] Create policies.html section template with placeholder content in src/video_policy_orchestrator/server/ui/templates/sections/policies.html
- [ ] T017 [P] [US1] Create approvals.html section template with placeholder content in src/video_policy_orchestrator/server/ui/templates/sections/approvals.html
- [ ] T018 [US1] Implement section route handlers for all 5 sections in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T019 [US1] Implement root redirect handler (/ -> /jobs) in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T020 [US1] Create 404.html error template in src/video_policy_orchestrator/server/ui/templates/errors/404.html
- [ ] T021 [US1] Implement 404 error handler middleware in src/video_policy_orchestrator/server/ui/routes.py

**Checkpoint**: User Story 1 complete - all 5 sections accessible via navigation, root redirects to /jobs, 404 shows friendly error

**Commit**: After Phase 3 completion, commit with message "feat(013): Implement section navigation and route handlers (US1)"

---

## Phase 4: User Story 2 - View Current Section Context (Priority: P2)

**Goal**: Visually highlight the currently active navigation link so users know which section they are viewing

**Independent Test**: Navigate to each section, verify the corresponding nav link has distinct visual styling (e.g., different background, border, or text weight)

### Implementation for User Story 2

- [ ] T022 [US2] Add CSS styles for active navigation state (.nav-link.active) in src/video_policy_orchestrator/server/static/css/main.css
- [ ] T023 [US2] Update base.html template to apply active class based on current section in src/video_policy_orchestrator/server/ui/templates/base.html
- [ ] T024 [US2] Create nav.js with client-side active state detection as fallback in src/video_policy_orchestrator/server/static/js/nav.js
- [ ] T025 [US2] Ensure template context passes active_id to navigation rendering in src/video_policy_orchestrator/server/ui/routes.py

**Checkpoint**: User Story 2 complete - active section is visually distinct in navigation

**Commit**: After Phase 4 completion, commit with message "feat(013): Add active navigation state highlighting (US2)"

---

## Phase 5: User Story 3 - Use UI on Different Devices (Priority: P3)

**Goal**: Make the UI layout responsive for laptop (1024px+) and tablet (768px-1023px) viewports

**Independent Test**: Resize browser window between 768px and 1920px, verify navigation and content remain usable without overlap or broken layout

### Implementation for User Story 3

- [ ] T026 [US3] Implement CSS Grid layout for app shell (sidebar + content) in src/video_policy_orchestrator/server/static/css/main.css
- [ ] T027 [US3] Add media queries for tablet breakpoint (768px-1023px) with narrower sidebar in src/video_policy_orchestrator/server/static/css/main.css
- [ ] T028 [US3] Add media queries for desktop breakpoint (1024px+) with full sidebar in src/video_policy_orchestrator/server/static/css/main.css
- [ ] T029 [US3] Add graceful degradation styles for below 768px viewport in src/video_policy_orchestrator/server/static/css/main.css
- [ ] T030 [US3] Add viewport meta tag to base.html for proper mobile rendering in src/video_policy_orchestrator/server/ui/templates/base.html

**Checkpoint**: User Story 3 complete - layout adapts smoothly across supported viewport widths

**Commit**: After Phase 5 completion, commit with message "feat(013): Add responsive layout for tablet and laptop (US3)"

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final improvements affecting all user stories

- [ ] T031 [P] Add HTTP security headers (X-Content-Type-Options, X-Frame-Options) to responses in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T032 [P] Add Cache-Control headers for static files in src/video_policy_orchestrator/server/app.py
- [ ] T033 [P] Add CSS custom properties for theming (colors, spacing) in src/video_policy_orchestrator/server/static/css/main.css
- [ ] T034 Add structured request logging (path, method, status code, duration) for UI routes in src/video_policy_orchestrator/server/ui/routes.py
- [ ] T035 Run and validate quickstart.md manual test scenarios
- [ ] T036 Update documentation with Web UI usage instructions in docs/

**Checkpoint**: Feature complete - all user stories functional, polished, documented

**Commit**: After Phase 6 completion, commit with message "feat(013): Polish Web UI shell with security headers, logging, and docs"

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - US1 (Navigation) must complete before US2 (Active highlighting uses nav structure)
  - US3 (Responsive) can start after US1 or in parallel with US2
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1: Setup
    ↓
Phase 2: Foundational
    ↓
Phase 3: US1 (Navigation) ──────────────┐
    ↓                                   │
Phase 4: US2 (Active State)             │
    ↓                                   ↓
    └─────────────────────→ Phase 5: US3 (Responsive)
                               ↓
                          Phase 6: Polish
```

- **User Story 1 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (P2)**: Depends on US1 (needs navigation structure to highlight)
- **User Story 3 (P3)**: Depends on US1 (needs layout structure), can parallel with US2

### Within Each User Story

- Templates before route handlers (templates must exist to render)
- CSS styles can parallel with templates
- Route handlers after templates exist
- Core implementation before integration

### Parallel Opportunities

**Phase 1** (all parallel):
- T002, T003, T004 can run in parallel

**Phase 3 - US1** (section templates parallel):
- T013, T014, T015, T016, T017 can run in parallel

**Phase 6** (polish tasks parallel):
- T031, T032, T033 can run in parallel

---

## Parallel Example: User Story 1

```bash
# After T012 (base.html with nav) is complete, launch all section templates in parallel:
Task: "Create jobs.html section template in templates/sections/jobs.html"
Task: "Create library.html section template in templates/sections/library.html"
Task: "Create transcriptions.html section template in templates/sections/transcriptions.html"
Task: "Create policies.html section template in templates/sections/policies.html"
Task: "Create approvals.html section template in templates/sections/approvals.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test navigation between all 5 sections
5. Deploy/demo basic navigation shell

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test navigation → Deploy/Demo (MVP!)
3. Add User Story 2 → Test active highlighting → Deploy/Demo
4. Add User Story 3 → Test responsive layout → Deploy/Demo
5. Complete Polish → Production ready

### Single Developer Strategy

Execute phases in order:
1. Phase 1: Setup (commit)
2. Phase 2: Foundational (commit)
3. Phase 3: US1 Navigation (commit)
4. Phase 4: US2 Active State (commit)
5. Phase 5: US3 Responsive (commit)
6. Phase 6: Polish (commit)

---

## Notes

- [P] tasks = different files, no dependencies within same phase
- [Story] label maps task to specific user story for traceability
- Commit after each phase completion per user request
- All templates extend base.html for consistent navigation
- Static files (CSS/JS) are separate from templates
- No JavaScript frameworks - vanilla JS only for nav.js
- 768px minimum viewport per spec requirement
