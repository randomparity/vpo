# Implementation Plan: Plan Approve/Reject Actions

**Branch**: `027-plan-approve-reject` | **Date**: 2025-11-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/027-plan-approve-reject/spec.md`

## Summary

Add approve/reject action functionality to the plan detail view with proper job creation on approval. When an operator approves a pending plan, the system creates an APPLY-type execution job with priority scheduling (ahead of scan/transcode jobs), updates the plan status, and returns a link to the created job. Reject marks the plan as permanently rejected. Both actions require confirmation dialogs and include audit logging.

## Technical Context

**Language/Version**: Python 3.10+, JavaScript ES6+
**Primary Dependencies**: aiohttp (web server), SQLite (storage), Jinja2 (templates), vanilla JS (frontend)
**Storage**: SQLite database at `~/.vpo/library.db` - existing `jobs` and `plans` tables
**Testing**: pytest for Python, manual testing for JavaScript
**Target Platform**: Linux server, web browser clients
**Project Type**: Web application with server-rendered HTML and JavaScript enhancements
**Performance Goals**: Approve/reject actions complete within 2 seconds (per spec SC-001/002)
**Constraints**: Must use existing ConfirmationModal component, maintain existing API patterns
**Scale/Scope**: Single-user local deployment, low concurrency expected

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | ✅ Pass | Job `created_at` uses UTC ISO-8601 |
| II. Stable Identity | ✅ Pass | Uses UUIDv4 for job ID, plan ID as FK |
| III. Portable Paths | ✅ Pass | Uses existing path handling from PlanRecord |
| IV. Versioned Schemas | ✅ Pass | No schema changes needed - uses existing Job model |
| V. Idempotent Operations | ✅ Pass | Status transitions are validated; duplicate approvals return error |
| VI. IO Separation | ✅ Pass | Job creation in DB layer, handler in server layer |
| VII. Explicit Error Handling | ✅ Pass | InvalidPlanTransitionError for state conflicts |
| VIII. Structured Logging | ✅ Pass | FR-013 requires audit logging with operator context |
| XII. Safe Concurrency | ✅ Pass | Uses existing DaemonConnectionPool with transactions |
| XIII. Database Design | ✅ Pass | Uses existing normalized schema, operations module |
| XV. Stable CLI/API Contracts | ✅ Pass | Extends existing API response format |
| XVI. Dry-Run Default | N/A | Actions are explicit operator approval (not automatic) |

**Gate Result**: PASS - All applicable principles satisfied.

## Project Structure

### Documentation (this feature)

```text
specs/027-plan-approve-reject/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (no schema changes)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (API contract updates)
│   └── approve-api.yaml # Updated approve endpoint contract
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/video_policy_orchestrator/
├── db/
│   ├── models.py        # Existing Job, PlanRecord, insert_job
│   └── operations.py    # Existing update_plan_status, create_plan
├── jobs/
│   └── tracking.py      # Existing job creation patterns (reference)
└── server/
    ├── ui/
    │   ├── routes.py    # MODIFY: api_plan_approve_handler, api_plan_reject_handler
    │   └── models.py    # MODIFY: PlanActionResponse to include job_id
    └── static/
        └── js/
            └── plans.js # MODIFY: Add confirmation for approve, show job link

tests/
├── unit/
│   └── test_plan_actions.py  # NEW: Unit tests for approve/reject logic
└── integration/
    └── test_plan_api.py      # NEW: Integration tests for API endpoints
```

**Structure Decision**: Minimal changes to existing web application structure. Modifies server routes, models, and JavaScript. No new modules required.

## Complexity Tracking

No constitution violations requiring justification.
