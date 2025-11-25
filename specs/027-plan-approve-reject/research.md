# Research: Plan Approve/Reject Actions

**Feature**: 027-plan-approve-reject
**Date**: 2025-11-25

## Research Summary

This feature builds on existing infrastructure. All technical questions have been resolved through codebase analysis.

---

## 1. Job Creation Pattern

**Decision**: Use existing `insert_job()` function with `JobType.APPLY`

**Rationale**: The codebase already has a well-established pattern for job creation used by TRANSCODE and SCAN jobs. The APPLY job type is already defined in the `JobType` enum.

**Alternatives considered**:
- Creating a new helper function in `jobs/tracking.py` - Rejected because the existing `insert_job()` in `db/models.py` is sufficient and follows established patterns
- Inline job creation in the route handler - Rejected as it violates IO separation principle

**Key findings**:
- `Job` model at `db/models.py:290-328`
- `insert_job()` function at `db/models.py:853-899`
- `JobType.APPLY` already exists at `db/models.py:25`
- Example pattern from `cli/transcode.py:316-348` and `jobs/tracking.py:27-73`

---

## 2. Priority Queue Implementation

**Decision**: Set `priority=10` for APPLY jobs (lower number = higher priority)

**Rationale**: The existing job system uses an integer priority field where lower values run first. Default is 100. Setting APPLY jobs to 10 ensures they run ahead of scan (100) and transcode (100) jobs per the clarification requirement.

**Alternatives considered**:
- Adding a separate priority queue - Rejected as unnecessary; existing priority field handles this
- Using priority=1 - Rejected as too aggressive; leaves room for future higher-priority jobs
- Using priority=50 - Considered but 10 provides clearer separation from default 100

**Key findings**:
- `priority` field in Job model at `db/models.py:299`
- Default priority is 100 (implicit from existing code)
- `get_queued_jobs()` orders by `priority ASC, created_at ASC` at `db/models.py:1055-1082`
- Index exists: `idx_jobs_priority_created ON jobs(priority, created_at)`

---

## 3. Plan-Job Linking

**Decision**: Store execution job ID in a new field on PlanRecord after approval

**Rationale**: The plan needs to reference the created job for navigation and status tracking. The `job_id` field already exists on PlanRecord but is used for the originating batch job. We need to add an `execution_job_id` field.

**Update**: After further review, the existing `job_id` field on PlanRecord is documented as "reference to originating job (if batch)". For clarity and to avoid confusion, the execution job ID should be returned in the API response and stored as a new field.

**Alternatives considered**:
- Reusing existing `job_id` field - Rejected as it has different semantics (originating vs execution)
- Not storing the link - Rejected as FR-009 requires showing job link

**Key findings**:
- `PlanRecord.job_id` at `db/models.py:246` - used for originating batch job
- Schema change required: Add `execution_job_id` field to plans table
- Or: Return job_id in response only (stateless approach)

**Final Decision**: Use stateless approach - return `job_id` in API response without schema change. The job already stores `file_path` and can be queried. This avoids schema migration complexity.

---

## 4. API Response Enhancement

**Decision**: Add `job_id` field to `PlanActionResponse` for approve action

**Rationale**: FR-008 requires returning the created job ID. The existing `PlanActionResponse` dataclass needs a new optional field.

**Alternatives considered**:
- Creating a separate `ApproveResponse` type - Rejected for unnecessary complexity
- Embedding job info in the `plan` field - Rejected as job is a separate entity

**Key findings**:
- `PlanActionResponse` at `server/ui/models.py` (dataclass with success, plan, error fields)
- Current response pattern established in `routes.py:2122-2126`

---

## 5. Confirmation Modal Usage

**Decision**: Use existing `window.ConfirmationModal.show()` for both approve and reject

**Rationale**: The modal component already exists and is used for reject. Adding it to approve follows the same pattern and satisfies FR-003.

**Alternatives considered**:
- Browser native `confirm()` - Rejected for poor UX and accessibility
- Custom inline confirmation - Rejected as modal already exists

**Key findings**:
- `ConfirmationModal` at `server/static/js/components/confirmation-modal.js`
- Usage example in `plans.js:503-517` for reject
- Supports custom title, confirmText, cancelText options

---

## 6. Audit Logging

**Decision**: Use structured logging with `logger.info()` including plan_id, action, timestamp

**Rationale**: FR-013 requires audit logging. The codebase uses Python's logging module consistently. Structured logging follows Constitution Principle VIII.

**Alternatives considered**:
- Database audit table - Rejected as overkill for single-user deployment
- External logging service - Rejected per Constitution (no external services by default)

**Key findings**:
- Existing logging at `routes.py:2121` - `logger.info("Plan %s approved", plan_id[:8])`
- Need to enhance with operator context (currently not available in single-user mode)

---

## 7. Deleted File Handling

**Decision**: Check file existence before approval, warn but allow proceeding

**Rationale**: Edge case from spec - file may be deleted between plan creation and approval. Job will fail if file doesn't exist, but operator should be informed.

**Alternatives considered**:
- Block approval if file deleted - Rejected as too restrictive; operator may want to proceed anyway
- Silent failure at job execution - Rejected as poor UX

**Implementation**: Check `file_id` is not NULL and file exists. Include `file_deleted` flag in response if applicable.

---

## Dependencies Summary

| Dependency | Location | Usage |
|------------|----------|-------|
| Job model | `db/models.py:290-328` | Create APPLY job |
| insert_job | `db/models.py:853-899` | Persist job to DB |
| update_plan_status | `db/operations.py:472-512` | Update plan status |
| PlanActionResponse | `server/ui/models.py` | API response |
| ConfirmationModal | `static/js/components/confirmation-modal.js` | UI confirmation |
| DaemonConnectionPool | `db/connection.py` | Thread-safe DB access |

---

## Schema Impact

**No schema changes required** for minimum viable implementation:
- Job model already supports APPLY type
- Priority field already exists
- API response can include job_id without schema change
- PlanRecord.job_id keeps its original semantics (originating job)

**Optional future enhancement**:
- Add `execution_job_id` to plans table for direct linking
- Add plan_id to jobs table for reverse lookup
