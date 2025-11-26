# Job Queue Guide

VPO uses a job queue system for long-running operations like transcoding. Jobs are queued with `vpo transcode` and processed by a worker started with `vpo jobs start`.

## Quick Start

```bash
# Queue files for transcoding
vpo transcode --policy hevc.yaml /videos/*.mkv

# Start processing
vpo jobs start

# Check progress
vpo jobs list
```

## Job Queue Concepts

### Job States

| Status | Description |
|--------|-------------|
| `queued` | Waiting to be processed |
| `running` | Currently being processed by a worker |
| `completed` | Successfully finished |
| `failed` | Error occurred during processing |
| `cancelled` | Cancelled by user |

### Job Lifecycle

```text
QUEUED ──> RUNNING ──> COMPLETED
              │
              ├──> FAILED
              │
CANCELLED <───┘
```

Jobs transition from `queued` to `running` when claimed by a worker, then to `completed` or `failed` based on the outcome. Users can cancel queued jobs at any time.

## Command Reference

### vpo jobs list

List jobs in the queue:

```bash
# List all jobs
vpo jobs list

# Filter by status
vpo jobs list --status queued
vpo jobs list --status running
vpo jobs list --status failed

# Limit results
vpo jobs list --limit 20
```

Output:
```text
ID         STATUS       TYPE       FILE                                       PROG   CREATED
-----------------------------------------------------------------------------------------------
a1b2c3d4   running      transcode  Movie.Name.2023.mkv                        45%    2024-01-15 10:30
e5f6g7h8   queued       transcode  Another.Movie.mkv                          -      2024-01-15 10:31
```

### vpo jobs status

Show queue statistics:

```bash
vpo jobs status
```

Output:
```text
Job Queue Status
------------------------------
  Queued:       12
  Running:       1
  Completed:    45
  Failed:        2
  Cancelled:     0
------------------------------
  Total:        60
```

### vpo jobs start

Start the worker to process queued jobs:

```bash
# Process all queued jobs
vpo jobs start

# Process maximum 5 files
vpo jobs start --max-files 5

# Run for maximum 1 hour (3600 seconds)
vpo jobs start --max-duration 3600

# Stop at 6:00 AM (24-hour format)
vpo jobs start --end-by 06:00

# Limit CPU cores for transcoding
vpo jobs start --cpu-cores 4

# Skip automatic purge of old jobs
vpo jobs start --no-purge
```

The worker exits when:
- Queue is empty
- `--max-files` limit reached
- `--max-duration` limit reached
- `--end-by` time reached
- SIGTERM/SIGINT received (graceful shutdown)

### vpo jobs cancel

Cancel a queued job:

```bash
# Cancel by job ID (full or first 8 characters)
vpo jobs cancel a1b2c3d4
```

Only `queued` jobs can be cancelled. Running jobs will complete naturally.

### vpo jobs retry

Retry a failed or cancelled job:

```bash
vpo jobs retry a1b2c3d4
```

Resets the job status to `queued` for reprocessing.

### vpo jobs clear

Remove old jobs from the queue:

```bash
# Clear completed jobs (default)
vpo jobs clear

# Clear failed jobs
vpo jobs clear --status failed

# Clear cancelled jobs
vpo jobs clear --status cancelled

# Clear all finished jobs
vpo jobs clear --status all

# Skip confirmation
vpo jobs clear --force
```

### vpo jobs recover

Recover stale jobs from dead workers:

```bash
vpo jobs recover
```

Resets `running` jobs without recent heartbeat updates back to `queued`. Useful after crashes or unexpected termination.

### vpo jobs cleanup

Clean up old jobs, backups, and temp files:

```bash
# Preview what would be cleaned
vpo jobs cleanup --dry-run

# Clean jobs older than 7 days
vpo jobs cleanup --older-than 7

# Also remove .original backup files
vpo jobs cleanup --include-backups

# Clean up orphaned temp files
vpo jobs cleanup --remove-temp

# Skip confirmation
vpo jobs cleanup --force
```

## Scheduled Processing

### Cron Integration

Run transcoding during off-peak hours:

```cron
# Start at 10 PM, finish by 5:59 AM
0 22 * * * /usr/local/bin/vpo jobs start --end-by 05:59 >> /var/log/vpo.log 2>&1
```

### Systemd Service

Create `/etc/systemd/system/vpo-worker.service`:

```ini
[Unit]
Description=VPO Transcoding Worker
After=network.target

[Service]
Type=simple
User=media
ExecStart=/usr/local/bin/vpo jobs start --max-duration 28800
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable vpo-worker
sudo systemctl start vpo-worker
```

### Limits for Resource Control

Use limits to prevent resource exhaustion:

```bash
# Process 5 files per cron run
vpo jobs start --max-files 5

# Run for max 8 hours
vpo jobs start --max-duration 28800

# Finish before 6 AM (for overnight runs)
vpo jobs start --end-by 06:00

# Use only 4 CPU cores (leave headroom for other tasks)
vpo jobs start --cpu-cores 4
```

## Configuration

Default worker settings in `~/.vpo/config.yaml`:

```yaml
jobs:
  retention_days: 30      # Days to keep completed jobs
  auto_purge: true        # Purge old jobs on worker start
  temp_directory: null    # Temp dir for transcoding (null = source dir)
  backup_original: true   # Keep backup of original files

worker:
  max_files: null         # No limit by default
  max_duration: null      # No limit by default
  end_by: null            # No deadline by default
  cpu_cores: null         # Use all cores by default
```

## Monitoring Progress

### List Running Jobs

```bash
vpo jobs list --status running
```

### Watch Queue

Monitor the queue in real-time:

```bash
watch -n 5 'vpo jobs list --limit 10'
```

### Check Worker Logs

If using systemd:

```bash
journalctl -u vpo-worker -f
```

## Error Handling

### Failed Jobs

Check failed jobs:

```bash
vpo jobs list --status failed
```

View error details in the job record or logs.

### Retry Failed Jobs

```bash
# Retry a specific job
vpo jobs retry a1b2c3d4
```

### Recover Orphaned Jobs

If a worker crashes, jobs may be stuck in `running` state:

```bash
vpo jobs recover
```

This resets stale running jobs to `queued` for reprocessing.

## Best Practices

1. **Use dry-run first**: Preview transcoding before queueing
   ```bash
   vpo transcode --dry-run --policy hevc.yaml /videos/
   ```

2. **Set appropriate limits**: Prevent runaway processing
   ```bash
   vpo jobs start --max-files 10 --end-by 06:00
   ```

3. **Regular cleanup**: Keep the job database lean
   ```bash
   vpo jobs cleanup --older-than 7
   ```

4. **Monitor for failures**: Check failed jobs periodically
   ```bash
   vpo jobs list --status failed
   ```

5. **Backup originals**: Enable `backup_original` in config for safety

## Related Docs

- [Transcode Policy](transcode-policy.md) - Configuring transcoding settings
- [CLI Usage](cli-usage.md) - Command reference
- [Configuration](configuration.md) - Global settings
