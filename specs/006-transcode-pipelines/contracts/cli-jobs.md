# CLI Contract: vpo jobs

**Module**: `vpo.cli.jobs`
**Parent Command**: `vpo`

## Command Group: jobs

Manage transcoding and file movement jobs.

```
vpo jobs [COMMAND]
```

### Subcommands

| Command | Description |
|---------|-------------|
| `list` | List all jobs |
| `status` | Show detailed job status |
| `start` | Start worker to process queue |
| `cancel` | Cancel a queued or running job |
| `cleanup` | Remove old jobs and temp files |

---

## vpo jobs list

List all jobs with status and progress.

```
vpo jobs list [OPTIONS]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--status` | Choice | all | Filter by status: queued, running, completed, failed, cancelled, all |
| `--limit` | Integer | 50 | Maximum jobs to display |
| `--json` | Flag | False | Output as JSON |

### Output Format (Table)

```
ID        STATUS     PROGRESS  FILE                          CREATED
abc123    running    45.2%     /videos/movie.mkv             2025-01-15 10:30
def456    queued     0.0%      /videos/show.s01e01.mkv       2025-01-15 10:31
ghi789    completed  100.0%    /videos/documentary.mkv       2025-01-15 09:00
```

### Output Format (JSON)

```json
{
  "jobs": [
    {
      "id": "abc12345-...",
      "status": "running",
      "progress_percent": 45.2,
      "file_path": "/videos/movie.mkv",
      "job_type": "transcode",
      "created_at": "2025-01-15T10:30:00Z",
      "started_at": "2025-01-15T10:30:05Z"
    }
  ],
  "total": 3,
  "filtered": 3
}
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Database error |

---

## vpo jobs status

Show detailed status for a specific job.

```
vpo jobs status JOB_ID [OPTIONS]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `JOB_ID` | Yes | Job ID (UUID or short prefix) |

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--json` | Flag | False | Output as JSON |
| `--follow` | Flag | False | Follow progress (update every second) |

### Output Format (Human)

```
Job: abc12345-6789-...
Type: transcode
Status: running
Progress: 45.2% (1234/2730 frames)

Source: /videos/movie.mkv
Output: /videos/movie.hevc.mkv
Policy: default-transcode

Started: 2025-01-15 10:30:05 (5m 23s ago)
ETA: ~6m remaining

Current:
  Frame: 1234/2730
  Time: 00:45:12/01:41:30
  FPS: 42.3
  Bitrate: 4521 kbps
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Job not found |
| 2 | Database error |

---

## vpo jobs start

Start the job worker to process queued jobs.

```
vpo jobs start [OPTIONS]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--max-files` | Integer | None | Stop after N jobs completed |
| `--max-duration` | String | None | Stop after duration (e.g., "2h", "30m") |
| `--end-by` | String | None | Stop before time (e.g., "05:59", "23:00") |
| `--cpu-cores` | Integer | None | Limit CPU cores for FFmpeg |
| `--dry-run` | Flag | False | Show what would be processed |
| `--verbose` | Flag | False | Show detailed progress |

### Behavior

1. On startup:
   - Auto-purge old completed jobs (if configured)
   - Reset stale RUNNING jobs to QUEUED (crash recovery)

2. Processing loop:
   - Claim next QUEUED job (by priority, then created_at)
   - Execute job (transcode or move)
   - Update progress periodically
   - Mark COMPLETED or FAILED

3. Exit conditions:
   - Queue empty
   - `--max-files` limit reached
   - `--max-duration` elapsed
   - `--end-by` time reached
   - SIGTERM/SIGINT received

### Output Format

```
[10:30:05] Starting job worker
[10:30:05] Purged 12 old jobs (older than 30 days)
[10:30:06] Processing job abc123: /videos/movie.mkv
[10:30:06]   Transcoding: hevc @ CRF 20, max 1080p
[10:35:42]   Completed: /videos/movie.hevc.mkv (1.2 GB → 856 MB)
[10:35:43] Processing job def456: /videos/show.s01e01.mkv
[10:38:15]   Completed: /videos/show.s01e01.hevc.mkv
[10:38:16] Queue empty, exiting
[10:38:16] Processed 2 jobs in 8m 11s
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (all jobs completed or limit reached) |
| 1 | Error during processing |
| 2 | Database error |
| 130 | Interrupted (SIGINT) |
| 143 | Terminated (SIGTERM) |

---

## vpo jobs cancel

Cancel a queued or running job.

```
vpo jobs cancel JOB_ID [OPTIONS]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `JOB_ID` | Yes | Job ID (UUID or short prefix) |

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--force` | Flag | False | Cancel even if running |

### Behavior

- QUEUED jobs: Immediately marked CANCELLED
- RUNNING jobs: Requires `--force`; sends signal to worker
- COMPLETED/FAILED/CANCELLED: Error (already terminal)

### Output

```
Cancelled job abc123
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Job not found or cannot cancel |
| 2 | Database error |

---

## vpo jobs cleanup

Remove old jobs and associated temp/backup files.

```
vpo jobs cleanup [OPTIONS]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--older-than` | String | "30d" | Age threshold (e.g., "7d", "1w", "30d") |
| `--include-backups` | Flag | False | Also remove backup files |
| `--dry-run` | Flag | False | Show what would be removed |

### Behavior

1. Find jobs older than threshold in terminal states (COMPLETED, FAILED, CANCELLED)
2. Optionally remove associated backup files
3. Remove orphaned temp files (*.tmp, *.part)
4. Delete job records from database

### Output

```
Found 45 jobs older than 30 days
  - 38 completed
  - 5 failed
  - 2 cancelled

Removing 45 job records...
Removing 12 backup files (8.5 GB)...
Removing 3 orphaned temp files (2.1 GB)...

Cleanup complete: freed 10.6 GB
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error during cleanup |
| 2 | Database error |
