# Research: Transcoding & File Movement Pipelines

**Date**: 2025-11-22
**Feature**: 006-transcode-pipelines

## Research Topics

### 1. FFmpeg Transcoding Integration

**Decision**: Use FFmpeg for all transcoding operations via subprocess with progress parsing.

**Rationale**:
- FFmpeg already detected by VPO's tool registry (see `tools/detection.py`)
- Supports all required codecs (H.264, H.265/HEVC, VP9, AV1)
- CRF and bitrate modes natively supported
- Progress output parseable via `-progress pipe:1` flag
- Well-documented, stable CLI interface

**Alternatives Considered**:
- HandBrake CLI: More user-friendly defaults but less granular control over parameters
- Direct libav bindings: Higher performance but significant complexity; FFmpeg subprocess sufficient for this use case

**Implementation Notes**:
- Use `-progress pipe:1 -stats_period 1` for real-time progress
- Parse `frame=`, `fps=`, `out_time=` for progress percentage
- Use `-threads N` to respect `--cpu-cores` limit (FR-030)
- Hardware acceleration (NVENC, QSV) deferred to future enhancement

### 2. Job Queue Design

**Decision**: SQLite-backed job queue in existing `library.db` with atomic state transitions.

**Rationale**:
- Consistent with existing VPO architecture (files, tracks, operations tables)
- SQLite supports atomic updates, sufficient for single-worker model
- No additional infrastructure required (no Redis, no separate daemon)
- Persists across CLI invocations naturally

**Alternatives Considered**:
- Separate job database file: Unnecessary complexity; single DB simpler
- In-memory queue: Doesn't persist; loses jobs on crash
- Celery/Redis: Over-engineered for single-worker CLI tool

**Implementation Notes**:
- Job states: QUEUED → RUNNING → COMPLETED/FAILED/CANCELLED
- Use `BEGIN IMMEDIATE` for atomic job claim (prevents race on concurrent `vpo jobs start`)
- Store progress as JSON blob (frame count, time position, percentage)
- Include `worker_pid` column for crash detection

### 3. Worker Process Model

**Decision**: Single foreground worker invoked via `vpo jobs start`, exits when queue empty or limit reached.

**Rationale**:
- Matches clarified requirement (cron/systemd integration)
- Simpler than daemon model; no PID files, no service management
- Limits (`--max-files`, `--max-duration`, `--end-by`, `--cpu-cores`) enable flexible scheduling
- Graceful shutdown on SIGTERM/SIGINT for systemd compatibility

**Alternatives Considered**:
- Background daemon with `vpo jobs daemon start/stop`: More complex; requires PID management
- Each transcode command blocks: Doesn't allow queue-ahead pattern
- Parallel workers: Increases complexity; single worker sufficient for most users

**Implementation Notes**:
- Check limits before starting each job (not just at startup)
- `--end-by` uses wall-clock comparison; finish current job before checking
- Write worker heartbeat to DB for stale job detection
- On startup, reset RUNNING jobs without active worker to QUEUED (crash recovery)

### 4. Filename Metadata Parsing

**Decision**: Regex-based filename parser with configurable patterns, following common naming conventions.

**Rationale**:
- Self-contained (no external API dependencies)
- Works offline
- Most media files follow predictable naming patterns
- Plugin hook allows future TMDb/TVDb integration (FR-036)

**Alternatives Considered**:
- Embedded metadata only: Often incomplete or missing in user-ripped files
- Mandatory external lookup: Requires API keys, network access, rate limiting

**Common Patterns to Support**:
```
Movies:
  Movie.Name.2023.1080p.BluRay.x264-GROUP.mkv
  Movie Name (2023) [1080p].mkv

TV Shows:
  Series.Name.S01E02.Episode.Title.720p.WEB-DL.mkv
  Series Name - S01E02 - Episode Title.mkv
  Series Name 1x02 Episode Title.mkv
```

**Implementation Notes**:
- Default patterns cover 90%+ of common naming conventions
- User can define custom patterns in config
- Extract: title, year, series, season, episode, resolution, source, codec
- Fallback values configurable per-template (default: "Unknown")

### 5. Audio Codec Preservation

**Decision**: Codec whitelist approach - codecs in `audio_preserve_codecs` are stream-copied; others processed per policy.

**Rationale**:
- Simple, declarative policy syntax
- Common lossless codecs: TrueHD, DTS-HD MA, FLAC, PCM
- User controls exactly which formats to preserve
- Matches user story (cinephile preserving high-quality audio)

**Codec Categories**:
```yaml
# Lossless (typically preserve)
- truehd      # Dolby TrueHD
- dts-hd      # DTS-HD Master Audio (dts-hd ma in ffprobe)
- flac
- pcm_*       # Any PCM variant

# Lossy HD (user choice)
- eac3        # Dolby Digital Plus
- dts         # DTS Core

# Lossy (typically transcode/remove)
- ac3         # Dolby Digital
- aac
- mp3
```

**Implementation Notes**:
- Match codec names against ffprobe output (normalize case)
- `audio_transcode_to`: Target codec for non-preserved tracks (default: aac)
- `audio_downmix`: Create additional stereo track if requested
- Per-track processing; language-agnostic (FR-015)

### 6. Safety and Backup Strategy

**Decision**: Write-to-temp-then-move pattern with optional original backup.

**Rationale**:
- Original file never modified in place during transcode
- Atomic move on completion ensures no partial files
- Backup provides user-recoverable original
- Aligns with Constitution XVI (Dry-Run Default) philosophy

**Flow**:
1. Validate source file exists and is readable
2. Check destination disk space (estimate output size)
3. Create temp file in configured temp_directory (or same dir with `.tmp` suffix)
4. Run FFmpeg writing to temp file
5. On success: optionally backup original → move temp to final location
6. On failure: delete temp file, original untouched

**Implementation Notes**:
- `backup_original: true` → rename original to `filename.original.ext` or move to backup dir
- `temp_directory` config option; falls back to same directory as source
- Disk space check: estimate output size from duration × bitrate (with 20% margin)
- Cleanup command removes `.original` files and temp files older than threshold

### 7. Job Retention and Cleanup

**Decision**: Configurable retention period with auto-purge on worker startup.

**Rationale**:
- Prevents unbounded DB growth
- Auto-purge integrates with normal workflow (no separate maintenance)
- Configurable meets diverse user needs (some want history, some don't)

**Configuration**:
```yaml
jobs:
  retention_days: 30  # Default: 30 days
  auto_purge: true    # Purge on vpo jobs start
```

**Implementation Notes**:
- Purge only COMPLETED/FAILED/CANCELLED jobs (never QUEUED/RUNNING)
- `vpo jobs cleanup` for manual purge with `--older-than` option
- Also cleans backup files and orphaned temp files

## Dependencies Summary

| Component | Dependency | Notes |
|-----------|------------|-------|
| Transcoding | FFmpeg | Already in tool registry |
| Progress parsing | FFmpeg `-progress` | Built-in feature |
| Job queue | SQLite | Existing library.db |
| Filename parsing | Python re | stdlib |
| Temp files | Python tempfile | stdlib |
| Time limits | Python datetime | stdlib |

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| FFmpeg not installed | Clear error message with install instructions (existing pattern) |
| Long transcode interrupted | Temp file deleted; original preserved; job marked FAILED |
| Disk full during transcode | Pre-flight space check; graceful failure |
| Concurrent workers | Single worker model; atomic job claim with `BEGIN IMMEDIATE` |
| Stale RUNNING jobs | Worker heartbeat; crash recovery on startup |

## Open Questions (Resolved)

All questions resolved during clarification phase. See spec.md Clarifications section.
