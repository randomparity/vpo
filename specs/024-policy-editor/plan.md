# Implementation Plan: Visual Policy Editor

**Branch**: `024-policy-editor` | **Date**: 2025-11-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/024-policy-editor/spec.md`

## Summary

Create a visual, form-based policy editor that allows users to edit core policy options (track ordering, language preferences, default flags, commentary patterns) without manually editing YAML. The editor must preserve unknown fields during round-trip operations and provide real-time YAML preview alongside the form interface.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: aiohttp, Jinja2, aiohttp-jinja2, PyYAML, pydantic
**Storage**: Filesystem (YAML files in ~/.vpo/policies/)
**Testing**: pytest, unit tests, integration tests
**Target Platform**: Linux and macOS (web server via aiohttp daemon)
**Project Type**: Web application (server-rendered HTML + vanilla JavaScript)
**Performance Goals**: Form interactions <100ms, save operations <1s, support policies up to 10KB
**Constraints**: Must preserve unknown YAML fields, must not lose comments (best-effort), client-side validation must mirror backend
**Scale/Scope**: Single policy editor page, ~5-8 form sections, support for ~50 policy files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ✅ Compliant Principles

- **I. Datetime Integrity**: No datetime values in this feature
- **II. Stable Identity**: Policy files identified by filename (existing pattern)
- **III. Portable Paths**: Using pathlib.Path for all file operations
- **IV. Versioned Schemas**: Using existing PolicySchema with schema_version field
- **V. Idempotent Operations**: Saving same policy twice produces identical result
- **VI. IO Separation**: Policy loading/validation separated via loader.py
- **VII. Explicit Error Handling**: Will use PolicyValidationError and custom exceptions
- **VIII. Structured Logging**: Will log policy edits with policy name and operation
- **IX. Configuration as Data**: Policy files are data, no hardcoded paths
- **X. Policy Stability**: Not modifying PolicySchema, only adding editor UI
- **XI. Plugin Isolation**: No plugin interfaces affected
- **XII. Safe Concurrency**: No concurrent operations (single-user editor session)
- **XIII. Database Design**: No database changes (filesystem only)
- **XIV. Test Media Corpus**: Will add policy file fixtures for testing
- **XV. Stable CLI/API Contracts**: Adding new API endpoints, not modifying existing
- **XVI. Dry-Run Default**: Not applicable (editor preview is inherently safe)
- **XVII. Data Privacy**: All operations local, no external services
- **XVIII. Living Documentation**: Will update docs with editor usage guide

### ⚠️ YAML Comment Preservation Challenge

**Issue**: PyYAML's safe_load/safe_dump loses comments by design. The spec requires "best-effort" preservation of YAML comments.

**Resolution**: Document in Assumptions that structural preservation is best-effort due to library limitations. Consider using ruamel.yaml if comment preservation becomes critical in Phase 1 research.

## Project Structure

### Documentation (this feature)

```text
specs/024-policy-editor/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (API schemas)
│   └── api.yaml         # OpenAPI spec for policy editor endpoints
└── checklists/
    └── requirements.md  # Spec quality validation
```

### Source Code (repository root)

```text
src/vpo/
├── policy/
│   ├── loader.py          # [EXISTING] Policy loading/validation
│   ├── discovery.py       # [EXISTING] Policy file discovery
│   └── models.py          # [EXISTING] PolicySchema definitions
├── server/
│   ├── ui/
│   │   ├── routes.py      # [MODIFY] Add policy editor routes
│   │   ├── models.py      # [MODIFY] Add policy editor models
│   │   └── templates/
│   │       ├── policies.html          # [EXISTING] List view
│   │       └── policy_editor.html     # [NEW] Editor page
│   └── static/
│       ├── css/
│       │   └── policy-editor.css                  # [NEW] Editor styles
│       ├── data/
│       │   └── iso-639-2.json                     # [NEW] Language codes
│       └── js/
│           └── policy-editor/                     # [NEW] Editor modules
│               ├── state-manager.js               # Proxy-based reactive state
│               ├── form-bindings.js               # Two-way form sync
│               ├── yaml-preview.js                # Real-time YAML generation
│               ├── track-ordering.js              # Track order controls
│               ├── language-autocomplete.js       # Accessible autocomplete
│               ├── language-list.js               # Reorderable language list
│               ├── commentary-patterns.js         # Commentary pattern editor
│               ├── validators.js                  # Client-side validation
│               └── policy-editor.js               # Main module coordinator

tests/
├── unit/
│   ├── server/
│   │   └── test_policy_editor_routes.py  # [NEW] Route unit tests
│   └── policy/
│       └── test_policy_roundtrip.py      # [NEW] Field preservation tests
└── integration/
    └── test_policy_editor_flow.py        # [NEW] E2E editor tests
```

**Structure Decision**: Web application structure. Backend logic in src/vpo/server/ui/, frontend assets in server/static/. Follows existing VPO web UI pattern (023-policies-list-view).

## Complexity Tracking

No violations requiring justification. Implementation follows existing patterns and principles.

---

## Phase 0: Outline & Research

### Research Tasks

1. **YAML Preservation Strategies**
   - Question: How can we preserve unknown fields and comments when round-tripping YAML?
   - Context: PyYAML safe_load/safe_dump loses comments
   - Options: ruamel.yaml (preserves comments), custom merge strategy
   - Deliverable: Recommendation in research.md

2. **Form State Management Pattern**
   - Question: How should we manage form state in vanilla JavaScript?
   - Context: No frameworks, need reactive YAML preview
   - Options: Event-driven updates, Proxy-based reactivity, explicit sync
   - Deliverable: Pattern recommendation with example

3. **Validation Strategy**
   - Question: How do we mirror backend validation in the frontend?
   - Context: Need to catch errors before save
   - Options: Duplicate logic in JS, fetch validation endpoint, hybrid
   - Deliverable: Validation architecture recommendation

4. **Language Code Input**
   - Question: How should users input ISO 639-2 language codes?
   - Context: Must be valid 2-3 letter codes
   - Options: Free text with validation, dropdown with common codes, autocomplete
   - Deliverable: UX recommendation

### Research Deliverable

Create `research.md` with:
- **Decision**: Chosen approach for each research task
- **Rationale**: Why this approach fits VPO's constraints
- **Alternatives Considered**: What else was evaluated and why rejected
- **Implementation Notes**: Key details for Phase 1

---

## Phase 1: Design & Contracts

### Artifacts

1. **data-model.md**: Document the editor data flow
   - Frontend form state structure
   - API request/response models
   - YAML round-trip process
   - Validation rules per field

2. **contracts/api.yaml**: OpenAPI specification
   - GET /api/policies/{name} - Fetch policy for editing
   - PUT /api/policies/{name} - Save policy changes
   - Request/response schemas
   - Error response formats

3. **quickstart.md**: Developer onboarding
   - How to run the editor locally
   - How to add a new form field
   - How to test policy round-trip
   - How to debug validation errors

4. **Agent Context Update**: Run `.specify/scripts/bash/update-agent-context.sh claude`
   - Add: aiohttp-jinja2 (existing), vanilla JavaScript pattern
   - Preserve: Existing web UI technologies

---

## Phase 2: Implementation Tasks (Generated by /speckit.tasks)

Phase 2 tasks will be generated by the `/speckit.tasks` command after Phase 1 design is complete. Tasks will cover:

- Backend API endpoint implementation
- Frontend form component development
- YAML round-trip logic with field preservation
- Form validation (client and server)
- Integration testing
- Documentation updates

---

## Gates & Validation

### Phase 0 → Phase 1 Gate
- [ ] All research questions answered in research.md
- [ ] YAML preservation strategy chosen
- [ ] Form state management pattern documented
- [ ] Validation approach defined

### Phase 1 → Phase 2 Gate
- [ ] data-model.md complete with all entities
- [ ] API contracts defined in contracts/api.yaml
- [ ] quickstart.md provides clear setup instructions
- [ ] Agent context updated with new technologies
- [ ] Constitution re-check passes

### Phase 2 Completion Gate (handled by /speckit.tasks)
- [ ] All functional requirements from spec.md implemented
- [ ] Unit tests cover policy round-trip and validation
- [ ] Integration tests cover full editor flow
- [ ] Manual testing confirms YAML preservation
- [ ] Documentation updated

---

**Next Step**: Begin Phase 0 research by spawning research agents to answer the 4 research questions above.
