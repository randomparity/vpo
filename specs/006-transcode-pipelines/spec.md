# Feature Specification: Transcoding & File Movement Pipelines

**Feature Branch**: `006-transcode-pipelines`
**Created**: 2025-11-22
**Status**: Draft
**Input**: User description: "Transcoding & File Movement Pipelines - Job system for long-running tasks, policies for transcoding, audio preservation rules, and directory organization"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Transcode Video with Quality Policy (Priority: P1)

As a user, I want to specify a target video codec and quality settings (e.g., H.265 at CRF 20) in my policy so that VPO can recompress video files while preserving the tracks I've selected through existing policy rules.

**Why this priority**: Transcoding is the core value proposition of this feature. Users need to reduce file sizes or standardize codecs across their library while maintaining quality control. This enables all other stories.

**Independent Test**: Can be fully tested by defining a transcoding policy and running it against a test video file, verifying the output uses the correct codec and quality settings.

**Acceptance Scenarios**:

1. **Given** a policy with `target_video_codec: hevc` and `target_crf: 20`, **When** the user runs the transcode command on an H.264 file, **Then** the output file is encoded with H.265 at CRF 20
2. **Given** a policy with `max_resolution: 1080p`, **When** the user runs the transcode command on a 4K file, **Then** the output file is downscaled to 1080p
3. **Given** a policy with transcoding settings, **When** the user runs with `--dry-run`, **Then** the system displays estimated output size and duration without modifying any files
4. **Given** a file already matching the target codec and quality, **When** the user runs the transcode command, **Then** the system skips transcoding and reports "already compliant"

---

### User Story 2 - Job Queue for Long-Running Tasks (Priority: P1)

As a user, I want VPO to queue transcoding and move operations as background jobs so that I can submit multiple files for processing without blocking the CLI and monitor their progress.

**Why this priority**: Transcoding operations can take hours. Without a job queue, users cannot process multiple files efficiently or monitor progress. This is essential infrastructure for practical use.

**Independent Test**: Can be fully tested by submitting multiple transcode jobs and verifying they are queued, processed sequentially, and their status can be monitored via CLI.

**Acceptance Scenarios**:

1. **Given** a transcode command is submitted, **When** the operation begins, **Then** a job record is created with status "queued"
2. **Given** queued jobs exist, **When** the user runs `vpo jobs start`, **Then** jobs are processed sequentially until queue is empty or limits are reached
3. **Given** multiple transcode jobs are submitted, **When** the user runs `vpo jobs list`, **Then** they see all jobs with their current status, progress percentage, and estimated time remaining
4. **Given** a job is in progress, **When** the user runs `vpo jobs status <job-id>`, **Then** they see detailed progress including current frame/time position
5. **Given** a running job, **When** the user runs `vpo jobs cancel <job-id>`, **Then** the job is stopped gracefully and marked as "cancelled"
6. **Given** a worker running with `--end-by 05:59`, **When** the wall-clock time approaches 05:59, **Then** the worker finishes the current job and exits without starting new jobs

---

### User Story 3 - Audio Track Preservation Rules (Priority: P2)

As a cinephile, I want to define which audio codecs to preserve in their original format (e.g., DTS-HD MA, TrueHD) and which to transcode or remove, so that I maintain high-fidelity audio while standardizing other tracks.

**Why this priority**: Audio preservation is critical for quality-conscious users but depends on the transcoding infrastructure from P1. It enhances the core transcoding feature with nuanced audio handling.

**Independent Test**: Can be fully tested by creating a policy with audio preservation rules and running it against a multi-track audio file, verifying preserved tracks remain untouched and others are processed as specified.

**Acceptance Scenarios**:

1. **Given** a policy with `audio_preserve_codecs: [truehd, dts-hd]`, **When** processing a file with TrueHD and AC3 tracks, **Then** the TrueHD track is copied without re-encoding and the AC3 track is processed per policy
2. **Given** a policy with `audio_transcode_to: aac` for non-preserved codecs, **When** processing a file with DTS (core) audio, **Then** the DTS track is transcoded to AAC
3. **Given** a policy with `audio_downmix: stereo` for compatibility tracks, **When** processing, **Then** an additional stereo track is created from the primary audio source
4. **Given** a multi-language file with mixed audio codecs, **When** applying preservation rules, **Then** each track is handled according to its codec regardless of language

---

### User Story 4 - Directory Organization Policies (Priority: P2)

As a user, I want to define directory organization rules in my policy using metadata templates (e.g., `Movies/{year}/{title}`) so that processed files are automatically moved to the correct location.

**Why this priority**: File organization adds significant value to the transcoding workflow but is independent of the transcoding logic itself. It can be implemented after core transcoding is stable.

**Independent Test**: Can be fully tested by defining a destination template and processing a file, verifying it is moved to the correct path based on its metadata.

**Acceptance Scenarios**:

1. **Given** a policy with `destination: "Movies/{year}/{title}"`, **When** processing a file with year=2023 and title="Test Movie", **Then** the output file is placed in `Movies/2023/Test Movie/`
2. **Given** a policy with `destination: "TV/{series}/{season}"`, **When** processing a TV episode, **Then** the file is moved to the appropriate series/season folder
3. **Given** a destination template referencing missing metadata, **When** processing a file without that metadata, **Then** the system uses a fallback value (e.g., "Unknown") or reports an error based on configuration
4. **Given** a move operation with `--dry-run`, **When** the user runs the command, **Then** the system displays the intended destination path without moving any files

---

### User Story 5 - Safety and Rollback Options (Priority: P2)

As a careful user, I want configuration options for backups and temporary files so that I can recover from failed transcoding or move operations.

**Why this priority**: Safety features protect user data but are not required for basic functionality. They enhance reliability once core features are working.

**Independent Test**: Can be fully tested by configuring backup options, running a transcode that fails mid-process, and verifying the original file is preserved and recoverable.

**Acceptance Scenarios**:

1. **Given** a configuration with `backup_original: true`, **When** a transcode completes successfully, **Then** the original file is renamed with a `.original` suffix (or moved to a backup directory)
2. **Given** a configuration with `temp_directory: /path/to/temp`, **When** transcoding begins, **Then** output is written to the temp directory and only moved to the final location on success
3. **Given** a transcode job that fails mid-process, **When** the failure is detected, **Then** the original file remains untouched and the partial output is cleaned up
4. **Given** a completed job with backup enabled, **When** the user runs `vpo jobs cleanup --older-than 7d`, **Then** backup files older than 7 days are removed
5. **Given** any transcoding or move operation, **When** it completes (success or failure), **Then** a detailed log entry is created with enough information to manually rollback if needed

---

### Edge Cases

- What happens when the destination disk runs out of space during transcoding?
  - System should detect low disk space before starting and warn; if space runs out mid-job, the job fails gracefully with original preserved
- How does the system handle files with corrupted segments?
  - Transcoding should fail with a clear error message identifying the corruption; original file remains untouched
- What happens when two jobs target the same output file?
  - Second job should be rejected or queued with a conflict warning
- How does the system handle symbolic links?
  - Symbolic links should be resolved to actual files; policy should have option to follow or ignore symlinks
- What happens when metadata extraction fails for directory organization?
  - System should use configurable fallback values or fail with a clear message
- How does the system handle concurrent access to the job queue?
  - Job queue operations should be atomic and handle concurrent CLI invocations safely
- What happens when a cancelled job has already written partial output?
  - Partial output should be cleaned up automatically on cancellation

## Requirements *(mandatory)*

### Functional Requirements

**Transcoding Policy**
- **FR-001**: System MUST support policy fields for target video codec (`target_video_codec`)
- **FR-002**: System MUST support policy fields for quality settings (`target_crf`, `target_bitrate`)
- **FR-003**: System MUST support policy fields for resolution limits (`max_resolution`, `max_width`, `max_height`)
- **FR-004**: System MUST provide dry-run capability showing estimated output size
- **FR-005**: System MUST skip transcoding for files already meeting policy requirements

**Job System**
- **FR-006**: System MUST persist job state in the database with status, progress, and timing information
- **FR-007**: System MUST provide `vpo jobs list` command showing all jobs with status and progress
- **FR-008**: System MUST provide `vpo jobs status <job-id>` command for detailed job information
- **FR-009**: System MUST provide `vpo jobs cancel <job-id>` command for graceful job termination
- **FR-010**: System MUST support concurrent job submission without blocking the CLI
- **FR-011**: System MUST process jobs sequentially (single job at a time) to avoid resource contention
- **FR-026**: System MUST provide `vpo jobs start` command to invoke worker that processes queued jobs
- **FR-027**: System MUST support worker limits: `--max-files N` (stop after N jobs completed)
- **FR-028**: System MUST support worker limits: `--max-duration T` (stop after T minutes/hours elapsed)
- **FR-029**: System MUST support worker limits: `--end-by TIME` (stop before specified wall-clock time, e.g., 05:59)
- **FR-030**: System MUST support worker limits: `--cpu-cores N` (limit CPU cores used per job)
- **FR-031**: Worker MUST exit cleanly when any limit is reached, leaving remaining jobs in queued state
- **FR-032**: System MUST support configurable retention period for completed/failed/cancelled jobs in config file
- **FR-033**: Worker MUST auto-purge jobs older than configured retention period on startup

**Audio Preservation**
- **FR-012**: System MUST support policy field for codecs to preserve without re-encoding (`audio_preserve_codecs`)
- **FR-013**: System MUST support policy field for target codec for non-preserved audio (`audio_transcode_to`)
- **FR-014**: System MUST support policy field for creating downmixed compatibility tracks (`audio_downmix`)
- **FR-015**: System MUST handle multi-track audio files, applying rules per-track based on codec

**Directory Organization**
- **FR-016**: System MUST support destination templates with metadata placeholders in policy (`destination`)
- **FR-017**: System MUST support standard placeholders: `{title}`, `{year}`, `{series}`, `{season}`, `{episode}`, `{resolution}`, `{codec}`
- **FR-018**: System MUST create destination directories if they do not exist
- **FR-019**: System MUST handle missing metadata according to configuration (fallback value or error)
- **FR-034**: System MUST extract metadata from filenames using configurable regex patterns
- **FR-035**: System MUST support common naming conventions (e.g., `Title.Year.Resolution.Source.mkv`, `Series.S01E02.Title.mkv`)
- **FR-036**: System MUST expose metadata extraction as a plugin hook to allow external metadata providers in future

**Safety & Rollback**
- **FR-020**: System MUST support configuration option to backup original files (`backup_original`)
- **FR-021**: System MUST support configuration option for temporary output directory (`temp_directory`)
- **FR-022**: System MUST preserve original files until transcoding completes successfully
- **FR-023**: System MUST clean up partial output files on job failure or cancellation
- **FR-024**: System MUST log all operations with sufficient detail for manual rollback
- **FR-025**: System MUST provide `vpo jobs cleanup` command to remove old backups and temp files

### Key Entities

- **Job**: Represents a queued or running transcode/move operation. Key attributes: job ID, file path, job type (transcode/move), status (queued/running/completed/failed/cancelled), progress percentage, start time, end time, error message if failed, policy reference
- **TranscodePolicy**: Extension to existing policy schema with transcoding-specific fields. Key attributes: target video codec, quality settings (CRF/bitrate), resolution limits, audio preservation rules, destination template
- **AudioPreservationRule**: Defines how to handle audio tracks during transcoding. Key attributes: codecs to preserve, target codec for transcoding, downmix settings
- **DestinationTemplate**: Template string with metadata placeholders for file organization. Key attributes: template pattern, fallback values for missing metadata

## Clarifications

### Session 2025-11-22

- Q: How are queued jobs executed? → A: Worker process via `vpo jobs start` with configurable limits (max files, CPU cores, duration, end-by time) for cron/systemd integration
- Q: How long are completed/failed/cancelled jobs retained? → A: Configurable retention period in config file, auto-purged on `vpo jobs start`
- Q: Where does metadata for directory templates come from? → A: Filename parsing using configurable patterns (initial implementation); metadata extraction exposed as plugin hook for future external lookup (TMDb, TVDb, etc.)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can define transcoding settings in policy YAML and successfully transcode video files to the specified codec and quality
- **SC-002**: Users can submit transcoding jobs and continue using the CLI without waiting for completion
- **SC-003**: Users can view job queue status and progress at any time via CLI commands
- **SC-004**: Audio preservation rules correctly handle mixed-codec files, preserving lossless tracks while transcoding lossy tracks
- **SC-005**: Files are automatically organized into directories based on metadata templates after processing
- **SC-006**: Original files are never lost due to failed or cancelled operations when backup/safety features are enabled
- **SC-007**: Users can recover from any operation failure using logged information or backup files
- **SC-008**: Job queue operations complete within 1 second (excluding actual transcoding time)
- **SC-009**: Dry-run mode accurately displays intended operations for transcoding, moves, and audio handling without modifying any files
