# Data Model: Web UI REST API Endpoints

**Feature**: 028-webui-rest-api
**Date**: 2025-11-25

## Overview

This document describes the response data models used by the Web UI REST API. All models are implemented as Python dataclasses in `server/ui/models.py`.

## Core Entities

### Job

Background task representing a scan, apply, transcode, or move operation.

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Unique identifier |
| job_type | string | One of: scan, apply, transcode, move |
| status | string | One of: queued, running, completed, failed, cancelled |
| file_path | string | Path to the file being processed |
| policy_name | string? | Policy name (for apply jobs) |
| progress_percent | number | 0.0 to 100.0 |
| created_at | string | ISO-8601 timestamp (UTC) |
| started_at | string? | ISO-8601 timestamp (UTC) |
| completed_at | string? | ISO-8601 timestamp (UTC) |
| duration_seconds | integer? | Calculated from timestamps |
| error_message | string? | Error details if failed |
| summary | string? | Human-readable summary |
| has_logs | boolean | Whether log file exists |

### File

Media file in the library.

| Field | Type | Description |
|-------|------|-------------|
| id | integer | Unique identifier |
| path | string | Full file path |
| filename | string | File name only |
| directory | string | Parent directory path |
| extension | string | File extension |
| container_format | string? | MKV, MP4, etc. |
| size_bytes | integer | File size |
| size_human | string | Human-readable size (e.g., "1.5 GB") |
| modified_at | string | ISO-8601 timestamp |
| scanned_at | string | ISO-8601 timestamp |
| scan_status | string | ok, error, pending |
| scan_error | string? | Error message if scan failed |
| video_tracks | array | List of video track objects |
| audio_tracks | array | List of audio track objects |
| subtitle_tracks | array | List of subtitle track objects |

### Track

Media track within a file.

| Field | Type | Description |
|-------|------|-------------|
| index | integer | Track index in container |
| codec | string | Codec name (h264, aac, etc.) |
| language | string? | ISO 639 language code |
| title | string? | Track title |
| is_default | boolean | Default track flag |
| is_forced | boolean | Forced track flag |
| channels | integer? | Audio channel count |
| channel_layout | string? | e.g., "5.1", "stereo" |
| width | integer? | Video width (video only) |
| height | integer? | Video height (video only) |
| has_transcription | boolean? | Audio transcription available |

### Transcription

Audio track transcription result.

| Field | Type | Description |
|-------|------|-------------|
| id | integer | Unique identifier |
| track_id | integer | Reference to track |
| detected_language | string | ISO 639 language code |
| confidence_score | number | 0.0 to 1.0 |
| confidence_level | string | high, medium, low |
| track_classification | string | main, commentary, other |
| transcript_sample | string | First ~500 characters |
| transcript_html | string | HTML with keyword highlighting |
| plugin_name | string | Plugin that produced transcription |
| created_at | string | ISO-8601 timestamp |
| file_id | integer | Reference to parent file |
| filename | string | Parent file name |

### Policy

Policy configuration file.

| Field | Type | Description |
|-------|------|-------------|
| name | string | Policy name (filename without extension) |
| filename | string | Full filename |
| file_path | string | Absolute path |
| last_modified | string | ISO-8601 timestamp |
| schema_version | integer | Policy schema version |
| track_order | array | Track type ordering |
| audio_language_preference | array | Preferred audio languages |
| subtitle_language_preference | array | Preferred subtitle languages |
| commentary_patterns | array | Patterns identifying commentary |
| default_flags | object | Default track flag settings |
| has_transcode | boolean | Transcode section present |
| has_transcription | boolean | Transcription section present |
| is_default | boolean | Marked as default policy |
| parse_error | string? | Parse error if invalid |

### Plan

Pending action plan for a file.

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Unique identifier |
| file_id | integer? | Reference to file (null if deleted) |
| file_path | string | File path at plan creation |
| policy_name | string | Policy used to generate plan |
| status | string | pending, approved, rejected, applied, canceled |
| created_at | string | ISO-8601 timestamp |
| updated_at | string | ISO-8601 timestamp |
| actions_count | integer | Number of planned actions |
| actions_preview | string | Human-readable action summary |

## List Response Wrapper

All list endpoints return paginated responses with consistent structure:

| Field | Type | Description |
|-------|------|-------------|
| {items} | array | Resource-specific array (jobs, files, etc.) |
| total | integer | Total count matching filters |
| limit | integer | Page size |
| offset | integer | Current offset |
| has_filters | boolean | Whether filters are applied |

## Error Response

All errors use consistent structure:

| Field | Type | Description |
|-------|------|-------------|
| error | string | Human-readable error message |
| details | string? | Additional context |
| errors | array? | Validation errors (field, message, code) |

## State Transitions

### Job Status

```
queued → running → completed
              ↓
            failed
              ↓
         cancelled
```

### Plan Status

```
pending → approved → applied
    ↓
 rejected
    ↓
 canceled
```

Only `pending` plans can be approved or rejected.
