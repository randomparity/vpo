# Data Model: Plan Approve/Reject Actions

**Feature**: 027-plan-approve-reject
**Date**: 2025-11-25

## Overview

This feature uses existing data models with minimal modifications. No database schema changes are required.

## Existing Entities (No Changes)

### PlanRecord

Existing entity representing a planned change set. Used as-is.

| Field | Type | Description |
|-------|------|-------------|
| id | str (UUID) | Unique identifier |
| file_id | int \| None | FK to files.id |
| file_path | str | Cached file path |
| policy_name | str | Source policy name |
| policy_version | int | Policy version at evaluation |
| job_id | str \| None | Originating batch job ID |
| actions_json | str | Serialized PlannedAction list |
| action_count | int | Number of actions |
| requires_remux | bool | Whether remux needed |
| status | PlanStatus | Current status |
| created_at | str | ISO-8601 UTC timestamp |
| updated_at | str | ISO-8601 UTC timestamp |

**Status Values**: pending, approved, rejected, applied, canceled

### Job

Existing entity for background job execution. Used for APPLY jobs.

| Field | Type | Description |
|-------|------|-------------|
| id | str (UUID) | Unique identifier |
| file_id | int \| None | FK to files.id |
| file_path | str | Target file path |
| job_type | JobType | APPLY for plan execution |
| status | JobStatus | QUEUED initially |
| priority | int | 10 for APPLY (high priority) |
| policy_name | str | Policy name from plan |
| policy_json | str | Plan's actions_json |
| progress_percent | float | 0.0 initially |
| progress_json | str \| None | None initially |
| created_at | str | ISO-8601 UTC timestamp |
| started_at | str \| None | None initially |
| completed_at | str \| None | None initially |
| error_message | str \| None | None initially |

## Modified Response Models

### PlanActionResponse (Enhanced)

Add optional `job_id` field for approve responses.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| success | bool | Yes | Operation result |
| plan | PlanListItem \| None | No | Updated plan data |
| error | str \| None | No | Error message if failed |
| job_id | str \| None | No | **NEW**: Created job ID (approve only) |
| job_url | str \| None | No | **NEW**: URL to job detail (approve only) |

**Python dataclass update**:
```python
@dataclass
class PlanActionResponse:
    success: bool
    plan: PlanListItem | None = None
    error: str | None = None
    job_id: str | None = None  # NEW: execution job ID
    job_url: str | None = None  # NEW: job detail URL
```

## State Transitions

### Plan Status Transitions (Existing)

```
                    ┌─────────────┐
                    │   PENDING   │
                    └─────────────┘
                      /    |    \
                     /     |     \
                    ▼      ▼      ▼
           ┌──────────┐ ┌──────────┐ ┌──────────┐
           │ APPROVED │ │ REJECTED │ │ CANCELED │
           └──────────┘ └──────────┘ └──────────┘
                |                          ▲
                |                          │
                ▼                          │
           ┌──────────┐                    │
           │ APPLIED  │◄───────────────────┘
           └──────────┘     (if job fails before complete)
```

### Job Status Flow (For APPLY jobs)

```
QUEUED → RUNNING → COMPLETED
           │
           ▼
         FAILED
```

## Data Flow: Approve Action

```
1. Client: POST /api/plans/{plan_id}/approve

2. Server: api_plan_approve_handler
   a. Validate plan_id (UUID format)
   b. Load PlanRecord from DB
   c. Validate status == PENDING
   d. Check file exists (warn if deleted)
   e. Create Job record:
      - id: new UUIDv4
      - file_id: plan.file_id
      - file_path: plan.file_path
      - job_type: JobType.APPLY
      - status: JobStatus.QUEUED
      - priority: 10 (high priority)
      - policy_name: plan.policy_name
      - policy_json: plan.actions_json
      - created_at: now (UTC ISO-8601)
   f. Insert Job to DB
   g. Update plan status to APPROVED
   h. Log audit entry
   i. Return PlanActionResponse with job_id

3. Client: Show success toast with job link
```

## Data Flow: Reject Action

```
1. Client: Show confirmation modal
2. Client (on confirm): POST /api/plans/{plan_id}/reject

3. Server: api_plan_reject_handler
   a. Validate plan_id (UUID format)
   b. Load PlanRecord from DB
   c. Validate status == PENDING
   d. Update plan status to REJECTED
   e. Log audit entry
   f. Return PlanActionResponse

4. Client: Show success toast, refresh list
```

## Validation Rules

### Approve Action
- Plan must exist
- Plan status must be PENDING
- File existence check (warn if deleted, don't block)

### Reject Action
- Plan must exist
- Plan status must be PENDING

### Job Creation (on approve)
- Job ID must be unique UUIDv4
- File path must be non-empty
- Priority must be positive integer
- Created timestamp must be UTC ISO-8601

## Indexes Used

Existing indexes sufficient:
- `idx_plans_status` - Filter pending plans
- `idx_jobs_priority_created` - Queue ordering
- Primary keys on both tables
