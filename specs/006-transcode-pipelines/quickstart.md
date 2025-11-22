# Quickstart: Transcoding & File Movement Pipelines

## Prerequisites

- VPO installed and configured
- FFmpeg installed and available in PATH (or configured in `~/.vpo/config.yaml`)
- Media files scanned into VPO database (`vpo scan`)

## Basic Workflow

### 1. Create a Transcoding Policy

Create `~/policies/transcode.yaml`:

```yaml
schema_version: 2

# Transcode to HEVC at good quality
transcode:
  target_video_codec: hevc
  target_crf: 20
  max_resolution: 1080p

  # Preserve lossless audio, transcode others to AAC
  audio_preserve_codecs:
    - truehd
    - dts-hd
    - flac
  audio_transcode_to: aac
  audio_transcode_bitrate: 192k
```

### 2. Queue Files for Transcoding

```bash
# Queue a single file
vpo transcode --policy ~/policies/transcode.yaml /videos/movie.mkv

# Queue multiple files
vpo transcode --policy ~/policies/transcode.yaml /videos/*.mkv

# Queue a directory recursively
vpo transcode --policy ~/policies/transcode.yaml --recursive /videos/movies/

# Preview without queueing
vpo transcode --dry-run --policy ~/policies/transcode.yaml /videos/
```

### 3. Start the Worker

```bash
# Process all queued jobs
vpo jobs start

# Process with limits (for cron/systemd)
vpo jobs start --max-files 5 --end-by 06:00

# See progress during processing
vpo jobs start --verbose
```

### 4. Monitor Jobs

```bash
# List all jobs
vpo jobs list

# Filter by status
vpo jobs list --status running
vpo jobs list --status queued

# Get detailed status for a job
vpo jobs status abc123

# Follow progress in real-time
vpo jobs status abc123 --follow
```

### 5. Cancel or Cleanup

```bash
# Cancel a queued job
vpo jobs cancel abc123

# Cancel a running job
vpo jobs cancel abc123 --force

# Clean up old completed jobs
vpo jobs cleanup --older-than 7d
```

## Common Configurations

### Scheduled Processing (cron)

Run transcoding overnight, finish by 6 AM:

```cron
# Start processing at 10 PM, end by 5:59 AM
0 22 * * * /usr/local/bin/vpo jobs start --end-by 05:59 >> /var/log/vpo-transcode.log 2>&1
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
ExecStart=/usr/local/bin/vpo jobs start --max-duration 8h
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
```

### Directory Organization

Add destination templates to your policy:

```yaml
schema_version: 2

transcode:
  target_video_codec: hevc
  target_crf: 20

# Organize output by metadata
destination: "Processed/{year}/{title}"
destination_fallback: "Unknown"
```

Output structure:
```
Processed/
├── 2023/
│   ├── Movie Name/
│   │   └── Movie Name.mkv
│   └── Another Movie/
│       └── Another Movie.mkv
└── Unknown/
    └── unidentified-file.mkv
```

## Tips

### Check Job Queue Before Starting

```bash
# See what's queued
vpo jobs list --status queued

# Estimate processing time (rough)
vpo jobs list --json | jq '.jobs | length'
```

### Use Profiles for Common Settings

In `~/.vpo/config.yaml`:

```yaml
profiles:
  high-quality:
    policy: ~/policies/high-quality.yaml
  archive:
    policy: ~/policies/archive.yaml
```

Then:
```bash
vpo transcode --profile high-quality /videos/movie.mkv
```

### Preserve Original Files

In `~/.vpo/config.yaml`:

```yaml
jobs:
  backup_original: true
  temp_directory: /tmp/vpo
```

### Resource Management

Limit CPU usage for background processing:

```bash
# Use only 4 cores
vpo jobs start --cpu-cores 4

# Or set default in config
```

```yaml
worker:
  cpu_cores: 4
```
