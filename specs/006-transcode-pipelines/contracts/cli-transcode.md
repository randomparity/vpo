# CLI Contract: vpo transcode

**Module**: `vpo.cli.transcode`
**Parent Command**: `vpo`

## Command: transcode

Submit files for transcoding based on policy.

```
vpo transcode [OPTIONS] PATH...
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes (1+) | File(s) or directory to transcode |

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--policy` | Path | None | Policy file path |
| `--profile` | String | None | Named profile from config |
| `--codec` | Choice | None | Override target codec (h264, hevc, vp9, av1) |
| `--crf` | Integer | None | Override CRF value (0-51) |
| `--max-resolution` | Choice | None | Override max resolution |
| `--output` | Path | None | Output directory (default: same as source) |
| `--recursive` | Flag | False | Process directories recursively |
| `--dry-run` | Flag | False | Show what would be queued |
| `--priority` | Integer | 100 | Job priority (lower = higher priority) |
| `--json` | Flag | False | Output as JSON |

### Resolution Choices

- `480p` (854x480)
- `720p` (1280x720)
- `1080p` (1920x1080)
- `1440p` (2560x1440)
- `4k` (3840x2160)

### Behavior

1. Validate paths exist and are media files
2. Load policy (from `--policy`, `--profile`, or default)
3. Apply CLI overrides to policy
4. For each file:
   - Check if transcoding needed (skip if already compliant)
   - Create job record with QUEUED status
5. Report queued jobs

### Output Format (Human)

```
Scanning 3 files...

Queued:
  [abc123] movie.mkv → hevc @ CRF 20
  [def456] show.s01e01.mkv → hevc @ CRF 20

Skipped (already compliant):
  documentary.mkv (hevc, 1080p)

Queued 2 jobs. Run 'vpo jobs start' to process.
```

### Output Format (JSON)

```json
{
  "queued": [
    {
      "job_id": "abc12345-...",
      "file_path": "/videos/movie.mkv",
      "target_codec": "hevc",
      "target_crf": 20
    }
  ],
  "skipped": [
    {
      "file_path": "/videos/documentary.mkv",
      "reason": "already_compliant"
    }
  ],
  "errors": [],
  "summary": {
    "queued": 2,
    "skipped": 1,
    "errors": 0
  }
}
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (at least one job queued or all skipped) |
| 1 | No valid files found |
| 2 | Policy error |
| 3 | Database error |

---

## Example Usage

### Basic transcoding

```bash
# Transcode single file with default policy
vpo transcode /videos/movie.mkv

# Transcode with specific policy
vpo transcode --policy ~/policies/high-quality.yaml /videos/

# Transcode directory recursively
vpo transcode --recursive /videos/movies/
```

### Override settings

```bash
# Force HEVC at CRF 18
vpo transcode --codec hevc --crf 18 /videos/movie.mkv

# Limit to 1080p
vpo transcode --max-resolution 1080p /videos/4k-movie.mkv

# Output to different directory
vpo transcode --output /processed/ /videos/movie.mkv
```

### Dry run

```bash
# See what would be queued without creating jobs
vpo transcode --dry-run --recursive /videos/
```

### Batch with priority

```bash
# High priority job (process first)
vpo transcode --priority 10 /videos/urgent-movie.mkv

# Low priority (process after others)
vpo transcode --priority 200 /videos/backlog/
```
