# Research: Plans List View

**Feature**: 026-plans-list-view
**Date**: 2025-11-25
**Status**: Complete

## Research Tasks

### 1. Existing Plan Model and Storage

**Decision**: Extend the in-memory `Plan` model with a persisted `PlanRecord` for the approval workflow.

**Rationale**: The existing `Plan` dataclass in `policy/models.py` (lines 304-329) is designed for in-memory policy evaluation. It contains:
- `file_id`, `file_path`, `policy_version`
- `actions: tuple[PlannedAction, ...]`
- `requires_remux`, `created_at`

For the approval workflow, we need persistent storage with:
- Additional metadata: source policy name, job reference, status
- Queryable fields for filtering
- Status transitions for approve/reject workflow

**Alternatives considered**:
1. **Modify existing Plan class** - Rejected: Plan is frozen dataclass for policy evaluation; adding mutable status would break existing code
2. **Use operations table** - Rejected: Operations track executed changes, not pending approvals
3. **New plans table (selected)** - Clean separation between evaluation (Plan) and approval workflow (PlanRecord)

### 2. List View Architecture Pattern

**Decision**: Follow Jobs Dashboard pattern with server-rendered template + vanilla JavaScript.

**Rationale**: Jobs Dashboard (`server/ui/templates/sections/jobs.html`, `server/static/js/jobs.js`) provides a proven implementation with:
- Progressive loading states
- Filter bar with dropdowns
- Paginated table with clickable rows
- Polling for live updates
- Smart row updates (selective re-rendering)

**Alternatives considered**:
1. **React/Vue SPA** - Rejected: Project uses vanilla JS without frameworks (per CLAUDE.md)
2. **Server-only rendering** - Rejected: Requires full page reload for filtering/pagination
3. **Jobs Dashboard pattern (selected)** - Consistent with existing UI, proven patterns

### 3. Polling Implementation

**Decision**: Use existing VPOPolling module with 5-second default interval.

**Rationale**: The shared polling module (`server/static/js/polling.js`) provides:
- Exponential backoff after failures (3 failures → 10s initial delay, 2x multiplier, max 2 minutes)
- Visibility-aware polling (pauses when tab hidden)
- Connection status tracking
- Clean resource cleanup

Configuration from existing code:
```javascript
CONFIG = {
    DEFAULT_INTERVAL: 5000,      // 5 seconds
    MIN_INTERVAL: 2000,          // 2 seconds
    MAX_INTERVAL: 60000          // 60 seconds
};
```

**Alternatives considered**:
1. **WebSockets** - Rejected: Over-engineered for this use case; no existing WebSocket infrastructure
2. **Server-Sent Events** - Rejected: More complex than polling; limited browser support for reconnection
3. **VPOPolling module (selected)** - Proven, feature-rich, consistent with Jobs Dashboard

### 4. Database Schema Design

**Decision**: New `plans` table with foreign key to `files`, following `operations` table pattern.

**Rationale**: The existing `operations` table (schema.py) provides a template:
- UUID primary key (stable identity per Constitution II)
- ISO-8601 UTC timestamps (per Constitution I)
- JSON serialization for actions
- Status enum for lifecycle tracking

**Key differences from operations**:
- Plans are created before execution (dry-run output)
- Plans have approval statuses: pending, approved, rejected, applied, canceled
- Plans may reference a source job (if created by batch dry-run)

### 5. API Endpoint Design

**Decision**: REST endpoints following Jobs API pattern.

**Endpoints**:
- `GET /api/plans` - List plans with filtering and pagination
- `POST /api/plans/{id}/approve` - Approve a pending plan
- `POST /api/plans/{id}/reject` - Reject a pending plan

**Rationale**: Jobs API (`routes.py` lines 162-304) provides proven patterns:
- Query parameter parsing with `FilterParams.from_query()`
- Bounds checking (limit 1-100, offset >= 0)
- Thread-safe DB access via `asyncio.to_thread`
- Response model with pagination metadata

**Alternatives considered**:
1. **GraphQL** - Rejected: No existing GraphQL infrastructure
2. **PATCH /api/plans/{id}** - Rejected: Less explicit than dedicated action endpoints
3. **POST action endpoints (selected)** - Clear intent, easy to audit, idempotent

### 6. Status Transition Rules

**Decision**: Implement state machine for plan status transitions.

**Valid transitions**:
```
pending → approved (via approve action)
pending → rejected (via reject action)
pending → canceled (via cancel action or timeout)
approved → applied (via execution job)
approved → canceled (via cancel action)
```

**Invalid transitions** (return 400 error):
- Any transition from `applied`, `rejected`, or `canceled` (terminal states)
- Non-pending to approved/rejected

**Rationale**: Clear state machine prevents invalid operations and enables auditing.

### 7. Source Reference Handling

**Decision**: Store both policy_name and job_id as nullable fields; display "[Deleted]" for missing references.

**Rationale**: Per clarification Q3, plans must remain visible even when their source is deleted:
- Store `policy_name` (string) - policy may be renamed/deleted
- Store `job_id` (string, nullable) - only set if plan came from batch job
- Display logic: if policy not found, show "[Deleted]" indicator

### 8. Inline Action Buttons

**Decision**: Approve/Reject buttons in action column for pending plans only.

**Implementation**:
- Table has "Actions" column
- For status="pending": show Approve (green) and Reject (red) buttons
- For other statuses: show "-" or status badge
- Buttons trigger POST to action endpoint
- On success: update row status immediately, show toast notification
- On error: show error message, keep current state

**Rationale**: Per clarification Q1, inline actions improve workflow efficiency for processing multiple plans.

## Technology Stack Summary

| Component | Technology | Reference Pattern |
|-----------|------------|-------------------|
| Database | SQLite, schema v8 | operations table in schema.py |
| DB Models | Frozen dataclasses | db/models.py PlanRecord |
| DB Operations | Functions with Connection param | db/operations.py |
| API Routes | aiohttp handlers | server/ui/routes.py |
| API Models | Dataclasses with to_dict() | server/ui/models.py |
| Templates | Jinja2 | server/ui/templates/sections/ |
| JavaScript | Vanilla ES6+ | server/static/js/jobs.js |
| Polling | VPOPolling module | server/static/js/polling.js |
| Timestamps | ISO-8601 UTC | Existing patterns throughout |

## Open Items

None - all research questions resolved.
