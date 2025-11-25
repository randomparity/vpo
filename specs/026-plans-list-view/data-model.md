# Data Model: Plans List View

**Feature**: 026-plans-list-view
**Date**: 2025-11-25

## Entities

### PlanRecord (New)

Persisted representation of a planned change set awaiting approval.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | str | PK, UUID | Unique identifier (UUIDv4) |
| file_id | int | FK → files.id | Reference to the target file |
| file_path | str | NOT NULL | Cached file path (for display when file deleted) |
| policy_name | str | NOT NULL | Name of the policy that generated the plan |
| policy_version | int | NOT NULL | Version of the policy at evaluation time |
| job_id | str | NULL | Reference to originating job (if batch) |
| actions_json | str | NOT NULL | JSON-serialized list of PlannedAction |
| action_count | int | NOT NULL | Number of planned actions (cached for display) |
| requires_remux | bool | NOT NULL | Whether plan requires container remux |
| status | str | NOT NULL | Plan status enum value |
| created_at | str | NOT NULL | ISO-8601 UTC creation timestamp |
| updated_at | str | NOT NULL | ISO-8601 UTC last update timestamp |

**Notes**:
- `file_path` is cached at creation time to display even if file is deleted
- `action_count` is cached to avoid deserializing JSON for list display
- `updated_at` tracks last status change

### PlanStatus (Enum)

| Value | Description | Terminal |
|-------|-------------|----------|
| pending | Awaiting operator review | No |
| approved | Approved for execution | No |
| rejected | Rejected by operator | Yes |
| applied | Changes have been executed | Yes |
| canceled | Withdrawn by operator or system | Yes |

**State Transitions**:
```
pending → approved   (approve action)
pending → rejected   (reject action)
pending → canceled   (cancel action or timeout)
approved → applied   (execution job completes)
approved → canceled  (cancel action before execution)
```

### PlannedAction (Existing - in policy/models.py)

Already defined, no changes needed:

| Field | Type | Description |
|-------|------|-------------|
| action_type | ActionType | Type of change (REORDER, SET_DEFAULT, etc.) |
| track_index | int \| None | Target track index |
| current_value | Any | Current value before change |
| desired_value | Any | Desired value after change |
| track_id | str \| None | Track identifier |

### Source (Virtual Entity)

Represents the source reference displayed in the UI.

| Field | Type | Description |
|-------|------|-------------|
| policy_name | str | Policy name (from PlanRecord) |
| policy_exists | bool | Whether policy still exists in system |
| job_id | str \| None | Originating job ID (from PlanRecord) |
| job_exists | bool | Whether job record still exists |
| display_text | str | Human-readable source text |

**Display Logic**:
- If policy exists: `"Policy: {policy_name}"`
- If policy deleted: `"Policy: [Deleted]"`
- If job exists: append `" (Job: {job_id[:8]}...)"`
- If job deleted and job_id set: append `" (Job: [Deleted])"`

## Database Schema

### plans table (Schema v8)

```sql
CREATE TABLE plans (
    id TEXT PRIMARY KEY,
    file_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    policy_name TEXT NOT NULL,
    policy_version INTEGER NOT NULL,
    job_id TEXT,
    actions_json TEXT NOT NULL,
    action_count INTEGER NOT NULL,
    requires_remux INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE SET NULL
);

-- Indexes for common queries
CREATE INDEX idx_plans_status ON plans(status);
CREATE INDEX idx_plans_created_at ON plans(created_at DESC);
CREATE INDEX idx_plans_file_id ON plans(file_id);
CREATE INDEX idx_plans_policy_name ON plans(policy_name);
```

**Notes**:
- `ON DELETE SET NULL` for file_id allows plans to survive file deletion
- Indexes optimize filtering by status, time range, and source lookup
- `requires_remux` stored as INTEGER (0/1) per SQLite convention

### Migration (v7 → v8)

```sql
-- Migration script for schema version 8
CREATE TABLE plans (
    id TEXT PRIMARY KEY,
    file_id INTEGER,
    file_path TEXT NOT NULL,
    policy_name TEXT NOT NULL,
    policy_version INTEGER NOT NULL,
    job_id TEXT,
    actions_json TEXT NOT NULL,
    action_count INTEGER NOT NULL,
    requires_remux INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE SET NULL
);

CREATE INDEX idx_plans_status ON plans(status);
CREATE INDEX idx_plans_created_at ON plans(created_at DESC);
CREATE INDEX idx_plans_file_id ON plans(file_id);
CREATE INDEX idx_plans_policy_name ON plans(policy_name);

-- Update schema version
UPDATE schema_version SET version = 8;
```

## Relationships

```
┌──────────────┐       ┌──────────────┐
│    files     │       │    jobs      │
│──────────────│       │──────────────│
│ id (PK)      │◄──┐   │ id (PK)      │
│ path         │   │   │ ...          │
│ ...          │   │   └──────────────┘
└──────────────┘   │          ▲
                   │          │ (optional reference)
                   │          │
              ┌────┴──────────┴─┐
              │     plans       │
              │─────────────────│
              │ id (PK)         │
              │ file_id (FK)────┤
              │ job_id ─────────┘
              │ policy_name     │
              │ status          │
              │ ...             │
              └─────────────────┘
```

## Validation Rules

### PlanRecord

1. **id**: Must be valid UUIDv4 format
2. **file_path**: Must be non-empty string
3. **policy_name**: Must be non-empty string
4. **policy_version**: Must be positive integer
5. **actions_json**: Must be valid JSON array
6. **action_count**: Must be >= 0 and match parsed actions_json length
7. **status**: Must be valid PlanStatus value
8. **created_at**: Must be valid ISO-8601 UTC timestamp
9. **updated_at**: Must be valid ISO-8601 UTC timestamp, >= created_at

### Status Transitions

1. Only `pending` status can transition to `approved` or `rejected`
2. Only `pending` or `approved` status can transition to `canceled`
3. Only `approved` status can transition to `applied`
4. Terminal statuses (`rejected`, `applied`, `canceled`) cannot transition

## API View Models

### PlanListItem

View model for list display:

| Field | Type | Description |
|-------|------|-------------|
| id | str | Plan UUID |
| file_path | str | Target file path |
| policy_name | str | Source policy name |
| source_display | str | Formatted source text |
| action_count | int | Number of planned actions |
| status | str | Current status |
| status_display | str | Human-readable status |
| created_at | str | ISO-8601 timestamp |
| created_at_display | str | Relative time ("2 hours ago") |

### PlanFilterParams

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| status | str \| None | None | Filter by status |
| since | str \| None | None | Time range: "24h", "7d", "30d" |
| limit | int | 50 | Results per page (1-100) |
| offset | int | 0 | Pagination offset |

### PlanListResponse

| Field | Type | Description |
|-------|------|-------------|
| plans | list[PlanListItem] | List of plans |
| total | int | Total matching plans |
| limit | int | Applied limit |
| offset | int | Applied offset |
| has_filters | bool | Whether filters are active |
