# Feature Specification: Plan Approve/Reject Actions

**Feature Branch**: `027-plan-approve-reject`
**Created**: 2025-11-25
**Status**: Draft
**Input**: User description: "Add approve/reject actions for planned changes with UI controls to trigger downstream job creation or cancelation"

## Clarifications

### Session 2025-11-25

- Q: Where should the created job be queued relative to other pending jobs? → A: Priority queue - approved plans jump ahead of scan/transcode jobs
- Q: Should approve/reject actions be logged for audit purposes? → A: Log with operator context - record action, plan ID, timestamp, and operator identity (if available)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Approve Plan and Queue Job (Priority: P1)

An operator reviews a pending plan in the plans list view and decides the proposed changes are acceptable. They click "Approve and queue job" to approve the plan and create an execution job that will apply the planned changes to the media file.

**Why this priority**: Core functionality - without job creation, approval has no effect. This is the primary action operators need to execute planned changes.

**Independent Test**: Can be fully tested by navigating to the plans list, clicking approve on a pending plan, confirming the action, and verifying both the plan status change and job creation in the jobs queue.

**Acceptance Scenarios**:

1. **Given** a pending plan in the list view, **When** the operator clicks "Approve and queue job" and confirms, **Then** the plan status changes to "approved", an execution job is created in the jobs queue, and the operator sees a link to the new job.

2. **Given** a pending plan in the list view, **When** the operator clicks "Approve and queue job" and cancels the confirmation, **Then** no changes occur and the plan remains in pending status.

3. **Given** a plan in non-pending status (approved, rejected, applied, canceled), **When** the operator views the list, **Then** the "Approve and queue job" button is not shown.

---

### User Story 2 - Reject Plan (Priority: P1)

An operator reviews a pending plan and determines the proposed changes should not be applied. They click "Reject plan" to permanently mark the plan as rejected, preventing any future execution.

**Why this priority**: Critical for human-review workflows - operators must be able to decline unwanted changes.

**Independent Test**: Can be fully tested by navigating to the plans list, clicking reject on a pending plan, confirming the action, and verifying the plan status changes to rejected.

**Acceptance Scenarios**:

1. **Given** a pending plan in the list view, **When** the operator clicks "Reject plan" and confirms, **Then** the plan status changes to "rejected" and the UI reflects this terminal state.

2. **Given** a pending plan in the list view, **When** the operator clicks "Reject plan" and cancels the confirmation, **Then** no changes occur and the plan remains in pending status.

3. **Given** a plan in non-pending status, **When** the operator views the list, **Then** the "Reject plan" button is not shown.

---

### User Story 3 - Confirmation Dialogs (Priority: P2)

To prevent accidental approvals or rejections, the operator sees a confirmation dialog before either action takes effect. The dialog clearly explains the consequences of the action.

**Why this priority**: Safety mechanism - prevents costly mistakes but not essential for basic workflow operation.

**Independent Test**: Can be fully tested by clicking each action button and verifying the confirmation dialog appears with appropriate messaging before any state changes occur.

**Acceptance Scenarios**:

1. **Given** a pending plan, **When** the operator clicks "Approve and queue job", **Then** a confirmation dialog appears explaining that this will queue a job to apply changes.

2. **Given** a pending plan, **When** the operator clicks "Reject plan", **Then** a confirmation dialog appears warning that rejection is permanent and cannot be undone.

3. **Given** a confirmation dialog is open, **When** the operator presses Escape or clicks outside the dialog, **Then** the dialog closes without taking action.

---

### User Story 4 - Navigation After Approval (Priority: P2)

After successfully approving a plan and creating a job, the operator needs easy access to monitor the execution. The system provides a clear path to the newly created job.

**Why this priority**: Usability enhancement - operators need to monitor jobs but can find them through the jobs list if needed.

**Independent Test**: Can be tested by approving a plan and verifying the success state includes a visible link or redirect to the new job.

**Acceptance Scenarios**:

1. **Given** a plan has been approved successfully, **When** the approval completes, **Then** the operator sees a success message with a link to the created job.

2. **Given** a plan has been approved successfully from the list view, **When** the operator clicks the job link, **Then** they navigate to the job detail view.

---

### Edge Cases

- What happens when the plan's target file has been deleted?
  - The system should warn the operator during approval that the file no longer exists, and allow them to proceed (job will fail) or cancel.

- What happens when another operator approves/rejects the same plan concurrently?
  - The system should detect the conflict (plan already transitioned) and show an appropriate error message indicating the plan state has changed.

- What happens when the database is unavailable during an action?
  - The system should display an error message and leave the plan in its current state.

- What happens if the plan references a policy that has been deleted?
  - Approval should still work since the plan contains the serialized actions; the policy is not needed for execution.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST show "Approve and queue job" and "Reject plan" buttons on the plan detail view when plan status is "pending"
- **FR-002**: System MUST hide action buttons when plan status is not "pending" (approved, rejected, applied, canceled)
- **FR-003**: System MUST display a confirmation dialog before executing approve action
- **FR-004**: System MUST display a confirmation dialog before executing reject action, warning that rejection is permanent
- **FR-005**: System MUST create an execution job when a plan is approved, with priority scheduling ahead of scan/transcode jobs
- **FR-006**: System MUST update plan status to "approved" when approval succeeds
- **FR-007**: System MUST update plan status to "rejected" when rejection succeeds
- **FR-008**: System MUST return the created job ID in the approval response
- **FR-009**: System MUST display a link to the created job after successful approval
- **FR-010**: System MUST prevent double-submission during action processing (disable buttons, show loading state)
- **FR-011**: System MUST display appropriate error messages when actions fail
- **FR-012**: System MUST handle concurrent modification conflicts gracefully with clear error messaging
- **FR-013**: System MUST log approve/reject actions with operator context (action type, plan ID, timestamp, operator identity if available) for audit purposes

### Key Entities

- **Plan**: The existing PlanRecord entity representing a set of proposed changes to a media file. Statuses: pending, approved, rejected, applied, canceled.

- **Execution Job**: A job record representing the background task that applies the approved plan's changes to the target file. Type: APPLY. Links back to the originating plan.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Operators can approve a pending plan and have a job queued within 2 seconds of confirmation
- **SC-002**: Operators can reject a pending plan within 2 seconds of confirmation
- **SC-003**: 100% of approval/rejection attempts show a confirmation dialog before execution
- **SC-004**: Zero accidental approvals or rejections occur due to missing confirmation dialogs
- **SC-005**: After approval, operators can navigate to the created job within one click
- **SC-006**: All action failures display user-friendly error messages explaining what went wrong

## Assumptions

- **Scope**: This feature implements approve/reject actions in the existing plans list view. A future plan detail view (if created) would reuse the same API endpoints and action patterns.
- The existing job infrastructure (Job, JobType.APPLY, jobs queue) is available and functional
- The existing confirmation modal component (ConfirmationModal) is available for use
- The plan's actions_json contains all information needed to execute the changes (no need to re-evaluate the policy)
