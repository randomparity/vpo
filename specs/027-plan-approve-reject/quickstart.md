# Quickstart: Plan Approve/Reject Actions

**Feature**: 027-plan-approve-reject
**Date**: 2025-11-25

## Overview

This feature adds approve/reject actions to the plans workflow. When an operator approves a plan, an execution job is created to apply the changes. Rejection marks the plan as permanently declined.

## Key Changes

### Backend (Python)

1. **Modify `api_plan_approve_handler`** in `server/ui/routes.py`:
   - Create APPLY job with priority=10
   - Return job_id and job_url in response
   - Add audit logging

2. **Modify `api_plan_reject_handler`** in `server/ui/routes.py`:
   - Add audit logging (already updates status)

3. **Modify `PlanActionResponse`** in `server/ui/models.py`:
   - Add `job_id: str | None` field
   - Add `job_url: str | None` field
   - Add `warning: str | None` field

### Frontend (JavaScript)

1. **Modify `handleApprove`** in `static/js/plans.js`:
   - Add confirmation dialog before action
   - Display job link in success toast

2. **Modify `handleReject`** in `static/js/plans.js`:
   - Already has confirmation dialog (no change needed)

## Implementation Checklist

### Phase 1: Backend - Job Creation
- [ ] Add job_id, job_url, warning fields to PlanActionResponse
- [ ] Create APPLY job in approve handler
- [ ] Set job priority to 10
- [ ] Return job_id in response
- [ ] Add audit logging with plan_id, action, timestamp

### Phase 2: Frontend - Confirmation & Navigation
- [ ] Add confirmation dialog to approve action
- [ ] Show job link in success toast
- [ ] Handle warning field (file deleted case)

### Phase 3: Testing
- [ ] Unit tests for job creation logic
- [ ] Integration tests for approve/reject endpoints
- [ ] Manual testing of UI flow

## Code Snippets

### Job Creation (approve handler)

```python
# In api_plan_approve_handler, after validating plan:

from video_policy_orchestrator.db.models import Job, JobType, JobStatus, insert_job

# Create execution job
job = Job(
    id=str(uuid.uuid4()),
    file_id=plan.file_id,
    file_path=plan.file_path,
    job_type=JobType.APPLY,
    status=JobStatus.QUEUED,
    priority=10,  # High priority (default is 100)
    policy_name=plan.policy_name,
    policy_json=plan.actions_json,
    progress_percent=0.0,
    progress_json=None,
    created_at=datetime.now(timezone.utc).isoformat(),
    started_at=None,
    completed_at=None,
    error_message=None,
)
insert_job(conn, job)
```

### Confirmation Dialog (JavaScript)

```javascript
// In handleApprove, before API call:

if (typeof window.ConfirmationModal !== 'undefined') {
    var confirmed = await window.ConfirmationModal.show(
        'This will queue a job to apply the planned changes to the file. Continue?',
        {
            title: 'Approve Plan',
            confirmText: 'Approve and Queue',
            cancelText: 'Cancel'
        }
    )
    if (!confirmed) {
        return
    }
}
```

### Success Toast with Job Link

```javascript
// In handleApprove, on success:

if (data.success) {
    var message = 'Plan approved successfully'
    if (data.job_url) {
        message += '. <a href="' + data.job_url + '">View job</a>'
    }
    showToast(message, 'success')
    fetchPlans()
}
```

## Testing

### Manual Test Cases

1. **Approve pending plan**
   - Navigate to plans list
   - Click Approve on a pending plan
   - Verify confirmation dialog appears
   - Confirm action
   - Verify plan status changes to "approved"
   - Verify job appears in jobs queue with high priority
   - Verify toast shows job link

2. **Reject pending plan**
   - Navigate to plans list
   - Click Reject on a pending plan
   - Verify confirmation dialog appears
   - Confirm action
   - Verify plan status changes to "rejected"

3. **Cancel confirmation**
   - Click Approve/Reject
   - Cancel the confirmation dialog
   - Verify plan status unchanged

4. **Concurrent modification**
   - Open two browser tabs on same plan
   - Approve in one tab
   - Try to approve/reject in other tab
   - Verify error message about state conflict

## Dependencies

| Component | Path | Action |
|-----------|------|--------|
| routes.py | `server/ui/routes.py` | Modify handlers |
| models.py | `server/ui/models.py` | Add response fields |
| plans.js | `server/static/js/plans.js` | Add confirmation |
| confirmation-modal.js | `server/static/js/components/` | Use existing |
| db/models.py | `db/models.py` | Use existing Job, insert_job |
