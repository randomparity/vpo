# Feature Specification: Processing Statistics and Metrics Tracking

**Feature Branch**: `040-processing-stats`
**Created**: 2025-12-01
**Status**: Draft
**Input**: User description: "GitHub Issue #225 - Add comprehensive processing statistics and metrics tracking"

## Clarifications

### Session 2025-12-01

- Q: What is the primary access interface for viewing statistics? → A: Both CLI and Web UI
- Q: How long should statistics data be retained? → A: Retain indefinitely, user can manually purge
- Q: What is the implementation scope for this sprint? → A: All 3 phases (Foundation, Per-Action Tracking, Performance & Quality)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Disk Space Savings (Priority: P1)

A user who has processed multiple video files wants to see how much disk space they have saved overall and per-file. After running `vpo process` on their library, they can query the system to see total bytes saved, percentage reduction, and savings broken down by policy.

**Why this priority**: Disk space savings is the primary value proposition for users running VPO. Without visibility into savings, users cannot measure the effectiveness of their policies or justify continued use.

**Independent Test**: Can be tested by processing a single file and immediately querying for size before/after metrics. Delivers immediate value by answering "How much space did I save?"

**Acceptance Scenarios**:

1. **Given** a file has been processed, **When** the user queries processing statistics, **Then** they see file size before processing, file size after processing, and bytes saved
2. **Given** multiple files have been processed, **When** the user queries aggregate statistics, **Then** they see total size savings across all files and average savings percentage
3. **Given** files were processed with different policies, **When** the user queries statistics by policy, **Then** they see savings grouped by policy name

---

### User Story 2 - Track Removed Content (Priority: P2)

A user wants to understand what content was removed from their files during processing. They need visibility into how many audio tracks, subtitle tracks, and attachments were removed per file and in aggregate.

**Why this priority**: Understanding track removal patterns helps users fine-tune their policies and verify the system is behaving as expected.

**Independent Test**: Can be tested by processing a file with multiple tracks and verifying track counts before/after are recorded accurately.

**Acceptance Scenarios**:

1. **Given** a file with multiple audio tracks has been processed, **When** the user views processing details, **Then** they see audio track count before and after, plus number removed
2. **Given** a file with subtitles has been processed, **When** the user views processing details, **Then** they see subtitle track count before and after, plus number removed
3. **Given** a file with font attachments has been processed, **When** the user views processing details, **Then** they see attachment count before and after, plus number removed

---

### User Story 3 - Analyze Policy Effectiveness (Priority: P2)

A user with multiple policies wants to compare which policies produce the best results. They can generate reports showing savings and track removal patterns grouped by policy.

**Why this priority**: Users often iterate on policies and need data to guide optimization decisions.

**Independent Test**: Can be tested by processing files with two different policies and comparing aggregated metrics.

**Acceptance Scenarios**:

1. **Given** files have been processed with different policies, **When** the user requests a policy comparison, **Then** they see average size savings per policy
2. **Given** a specific policy has been used multiple times, **When** the user views policy statistics, **Then** they see total files processed, success rate, and cumulative savings

---

### User Story 4 - Track Transcode Operations (Priority: P3)

A user who transcodes video or audio wants to see what codec transformations occurred. They need to know source codec, target codec, and whether transcoding was skipped due to skip conditions.

**Why this priority**: Transcode operations are computationally expensive; users need visibility to verify policies work correctly.

**Independent Test**: Can be tested by processing a file with video transcode enabled and verifying source/target codec are recorded.

**Acceptance Scenarios**:

1. **Given** a video file was transcoded, **When** the user views processing details, **Then** they see source video codec and target video codec
2. **Given** audio tracks were transcoded, **When** the user views processing details, **Then** they see count of audio tracks transcoded vs preserved
3. **Given** a transcode was skipped due to skip_if conditions, **When** the user views processing details, **Then** they see that transcoding was skipped and the reason

---

### User Story 5 - View Processing Performance (Priority: P3)

A user wants to understand how long processing takes and identify bottlenecks. They can see wall-clock time per phase and per operation.

**Why this priority**: Performance visibility helps users plan processing jobs and identify slow policies.

**Independent Test**: Can be tested by processing a file and verifying duration metrics are recorded for each phase.

**Acceptance Scenarios**:

1. **Given** a file has been processed, **When** the user views processing details, **Then** they see total processing duration in seconds
2. **Given** a multi-phase policy was applied, **When** the user views processing details, **Then** they see duration for each phase separately
3. **Given** multiple files have been processed, **When** the user queries aggregate statistics, **Then** they see average processing time per file

---

### Edge Cases

- What happens when processing fails mid-way? Partial statistics should still be recorded with error status.
- How are re-processed files handled? Each processing run creates a new statistics record; historical data is preserved.
- What happens when file size increases after processing (e.g., transcoding to higher quality)? Negative savings are recorded accurately.
- How are files with no changes handled? Zero-change processing is recorded with appropriate flags.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST record file size before and after each processing operation
- **FR-002**: System MUST calculate and store size change (bytes saved or added)
- **FR-003**: System MUST count audio tracks before and after processing and record number removed
- **FR-004**: System MUST count subtitle tracks before and after processing and record number removed
- **FR-005**: System MUST count attachments before and after processing and record number removed
- **FR-006**: System MUST record the policy name used for each processing operation
- **FR-007**: System MUST record processing duration (wall-clock time) for each operation
- **FR-008**: System MUST record success/failure status for each processing operation
- **FR-009**: System MUST record error messages when processing fails
- **FR-010**: System MUST record video transcode details (source codec, target codec) when applicable
- **FR-011**: System MUST record audio transcode summary (tracks transcoded vs preserved) when applicable
- **FR-012**: System MUST provide query capability for aggregate statistics by policy
- **FR-013**: System MUST provide query capability for aggregate statistics by time period
- **FR-014**: System MUST associate statistics with the file record via file_id
- **FR-015**: System MUST record number of phases completed for multi-phase policies
- **FR-016**: System MUST record total number of changes (actions) applied
- **FR-017**: System MUST expose statistics via CLI command (`vpo stats`)
- **FR-018**: System MUST expose statistics via Web UI dashboard
- **FR-019**: System MUST retain statistics indefinitely by default
- **FR-020**: System MUST provide manual purge capability for statistics data
- **FR-021**: System MUST record per-action results including action type, track affected, and before/after state
- **FR-022**: System MUST record the policy rule that triggered each action
- **FR-023**: System MUST record per-action duration
- **FR-024**: System MUST record per-phase wall-clock time
- **FR-025**: System MUST record I/O throughput metrics (bytes read/written)
- **FR-026**: System MUST parse and store FFmpeg encoding metrics (fps, bitrate) when available
- **FR-027**: System MUST record file hash before and after processing for integrity verification

### Key Entities

- **ProcessingStats**: Represents the outcome of a single processing operation on a file. Contains size metrics, track counts, timing, status, and policy reference. Associated with a FileRecord.
- **ActionResult**: Represents the outcome of an individual action within a processing operation. Contains action type, track information, before/after state, and result status. Associated with ProcessingStats.
- **PerformanceMetrics**: Represents detailed timing and throughput data for a processing operation. Contains per-phase timing and I/O metrics. Associated with ProcessingStats.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can query total disk space saved across their library within 2 seconds
- **SC-002**: Users can see per-file size savings immediately after processing completes
- **SC-003**: Users can identify which policy produces the highest average savings
- **SC-004**: Processing statistics are recorded for 100% of completed processing operations
- **SC-005**: Failed processing operations include error details sufficient to diagnose the issue
- **SC-006**: Historical statistics are preserved when files are re-processed
- **SC-007**: Users can generate a summary report of processing activity for any time period
