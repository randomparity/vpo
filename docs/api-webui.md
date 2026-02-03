# Web UI REST API Reference

**Version**: 1.0.0
**Base URL**: `http://localhost:8321` (default when running `vpo serve`)

This document describes the REST API endpoints available for the VPO Web UI. All endpoints return JSON responses and follow consistent patterns for pagination, error handling, and authentication.

## Conventions

### Request Format

- **Content-Type**: All request bodies must be `application/json`
- **Character Encoding**: UTF-8

### Response Format

All responses use JSON with the following conventions:

- **Timestamps**: ISO-8601 format in UTC (e.g., `2025-01-15T10:30:00+00:00`)
- **IDs**: Jobs and Plans use UUIDv4 strings; Files and Transcriptions use integers
- **Booleans**: JSON `true`/`false`

### Pagination

List endpoints support pagination with these query parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Page size (1-100) |
| `offset` | integer | 0 | Number of items to skip |

Paginated responses include:

```json
{
  "items": [...],
  "total": 150,
  "limit": 50,
  "offset": 0,
  "has_filters": false
}
```

---

## Jobs

Background tasks for scan, apply, transcode, and move operations.

### GET /api/jobs

List background jobs with optional filters.

**Query Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `status` | string | No | Filter by status: `queued`, `running`, `completed`, `failed`, `cancelled` |
| `type` | string | No | Filter by job type: `scan`, `apply`, `transcode`, `move` |
| `since` | string | No | Time filter: `24h`, `7d` |
| `limit` | integer | No | Page size (1-100, default 50) |
| `offset` | integer | No | Pagination offset (default 0) |

**Response**: `200 OK`

```json
{
  "jobs": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "job_type": "scan",
      "status": "completed",
      "file_path": "/media/movies",
      "progress_percent": 100.0,
      "created_at": "2025-01-15T10:00:00+00:00",
      "completed_at": "2025-01-15T10:05:32+00:00",
      "duration_seconds": 332
    }
  ],
  "total": 25,
  "limit": 50,
  "offset": 0,
  "has_filters": false
}
```

**Errors**:

- `400 Bad Request`: Invalid parameter value
- `503 Service Unavailable`: Database not available or service shutting down

---

### GET /api/jobs/{job_id}

Get detailed information about a specific job.

**Path Parameters**:

| Name | Type | Description |
|------|------|-------------|
| `job_id` | string (UUID) | Job identifier |

**Response**: `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "id_short": "550e8400",
  "job_type": "scan",
  "status": "completed",
  "priority": 100,
  "file_path": "/media/movies",
  "policy_name": null,
  "created_at": "2025-01-15T10:00:00+00:00",
  "started_at": "2025-01-15T10:00:01+00:00",
  "completed_at": "2025-01-15T10:05:32+00:00",
  "duration_seconds": 331,
  "progress_percent": 100.0,
  "error_message": null,
  "output_path": null,
  "summary": "Scanned 150 files, 148 successful, 2 errors",
  "summary_raw": {
    "files_scanned": 150,
    "files_successful": 148,
    "files_errored": 2
  },
  "has_logs": true
}
```

**Errors**:

- `400 Bad Request`: Invalid job ID format
- `404 Not Found`: Job not found
- `503 Service Unavailable`: Database not available

---

### GET /api/jobs/{job_id}/logs

Retrieve log output for a job.

**Path Parameters**:

| Name | Type | Description |
|------|------|-------------|
| `job_id` | string (UUID) | Job identifier |

**Query Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `lines` | integer | No | Number of lines to return (1-1000, default 500) |
| `offset` | integer | No | Line offset from start (default 0) |

**Response**: `200 OK`

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "lines": [
    "2025-01-15T10:00:01 INFO Starting scan...",
    "2025-01-15T10:00:02 INFO Processing /media/movies/file1.mkv",
    "2025-01-15T10:00:03 INFO Processing /media/movies/file2.mkv"
  ],
  "total_lines": 1500,
  "offset": 0,
  "has_more": true
}
```

**Errors**:

- `400 Bad Request`: Invalid job ID format
- `503 Service Unavailable`: Service shutting down

---

### GET /api/jobs/{job_id}/errors

Get scan errors for a scan job. Returns empty list for non-scan jobs.

**Path Parameters**:

| Name | Type | Description |
|------|------|-------------|
| `job_id` | string (UUID) | Job identifier |

**Response**: `200 OK`

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "errors": [
    {
      "path": "/media/movies/corrupted.mkv",
      "filename": "corrupted.mkv",
      "error": "ffprobe failed: Invalid data found when processing input"
    }
  ],
  "total_errors": 1
}
```

**Errors**:

- `400 Bad Request`: Invalid job ID format
- `503 Service Unavailable`: Database not available

---

## Library

Media files in the VPO library database.

### GET /api/library

List library files with optional filters.

**Query Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `status` | string | No | Filter by scan status: `ok`, `error` |
| `search` | string | No | Search in filename and path |
| `resolution` | string | No | Filter by resolution: `sd`, `720p`, `1080p`, `4k` |
| `audio_lang` | string[] | No | Filter by audio language(s), can specify multiple |
| `subtitles` | string | No | Filter by subtitle presence: `with`, `without` |
| `limit` | integer | No | Page size (1-100, default 50) |
| `offset` | integer | No | Pagination offset (default 0) |

**Response**: `200 OK`

```json
{
  "files": [
    {
      "id": 123,
      "filename": "Movie.2024.mkv",
      "path": "/media/movies/Movie.2024.mkv",
      "title": "Movie Title",
      "resolution": "1080p",
      "audio_languages": "eng, jpn",
      "scanned_at": "2025-01-15T10:00:00+00:00",
      "scan_status": "ok",
      "scan_error": null
    }
  ],
  "total": 1500,
  "limit": 50,
  "offset": 0,
  "has_filters": false
}
```

**Errors**:

- `503 Service Unavailable`: Database not available

---

### GET /api/library/{file_id}

Get detailed information about a specific file including all tracks.

**Path Parameters**:

| Name | Type | Description |
|------|------|-------------|
| `file_id` | integer | File identifier |

**Response**: `200 OK`

```json
{
  "file": {
    "id": 123,
    "path": "/media/movies/Movie.2024.mkv",
    "filename": "Movie.2024.mkv",
    "directory": "/media/movies",
    "extension": ".mkv",
    "container_format": "Matroska",
    "size_bytes": 4294967296,
    "size_human": "4.0 GB",
    "modified_at": "2024-12-01T12:00:00+00:00",
    "scanned_at": "2025-01-15T10:00:00+00:00",
    "scan_status": "ok",
    "scan_error": null,
    "scan_job_id": "550e8400-e29b-41d4-a716-446655440000",
    "video_tracks": [
      {
        "index": 0,
        "codec": "hevc",
        "language": null,
        "title": null,
        "is_default": true,
        "is_forced": false,
        "width": 1920,
        "height": 1080
      }
    ],
    "audio_tracks": [
      {
        "index": 1,
        "codec": "aac",
        "language": "eng",
        "title": "English Stereo",
        "is_default": true,
        "is_forced": false,
        "channels": 2,
        "channel_layout": "stereo",
        "has_transcription": true
      }
    ],
    "subtitle_tracks": [
      {
        "index": 2,
        "codec": "subrip",
        "language": "eng",
        "title": "English",
        "is_default": false,
        "is_forced": false
      }
    ],
    "other_tracks": []
  }
}
```

**Errors**:

- `400 Bad Request`: Invalid file ID format
- `404 Not Found`: File not found
- `503 Service Unavailable`: Database not available

---

### GET /api/library/languages

Get distinct audio languages present in the library for filter dropdowns.

**Response**: `200 OK`

```json
{
  "languages": [
    {"code": "eng", "name": "English", "count": 1200},
    {"code": "jpn", "name": "Japanese", "count": 350},
    {"code": "spa", "name": "Spanish", "count": 180}
  ]
}
```

**Errors**:

- `503 Service Unavailable`: Database not available

---

## Transcriptions

Audio track transcription results from language detection plugins.

### GET /api/transcriptions

List files with transcription information.

**Query Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `show_all` | boolean | No | If true, show all files (default: false, transcribed only) |
| `limit` | integer | No | Page size (1-100, default 50) |
| `offset` | integer | No | Pagination offset (default 0) |

**Response**: `200 OK`

```json
{
  "files": [
    {
      "id": 123,
      "filename": "Movie.2024.mkv",
      "path": "/media/movies/Movie.2024.mkv",
      "has_transcription": true,
      "detected_languages": "eng, jpn",
      "confidence_level": "high",
      "confidence_avg": 0.95,
      "transcription_count": 2,
      "scan_status": "ok"
    }
  ],
  "total": 500,
  "limit": 50,
  "offset": 0,
  "has_filters": false
}
```

**Errors**:

- `503 Service Unavailable`: Database not available

---

### GET /api/transcriptions/{transcription_id}

Get detailed transcription information for a specific audio track.

**Path Parameters**:

| Name | Type | Description |
|------|------|-------------|
| `transcription_id` | integer | Transcription identifier |

**Response**: `200 OK`

```json
{
  "transcription": {
    "id": 456,
    "track_id": 789,
    "detected_language": "eng",
    "confidence_score": 0.95,
    "confidence_level": "high",
    "track_classification": "main",
    "transcript_sample": "The quick brown fox jumps over...",
    "transcript_html": "<p>The quick brown fox jumps over...</p>",
    "transcript_truncated": true,
    "plugin_name": "whisper",
    "created_at": "2025-01-15T10:00:00+00:00",
    "updated_at": "2025-01-15T10:00:00+00:00",
    "track_index": 1,
    "track_codec": "aac",
    "original_language": "eng",
    "track_title": "English Stereo",
    "channels": 2,
    "channel_layout": "stereo",
    "is_default": true,
    "is_forced": false,
    "is_commentary": false,
    "classification_source": "metadata",
    "matched_keywords": [],
    "file_id": 123,
    "filename": "Movie.2024.mkv",
    "file_path": "/media/movies/Movie.2024.mkv"
  }
}
```

**Errors**:

- `400 Bad Request`: Invalid transcription ID format
- `404 Not Found`: Transcription not found
- `503 Service Unavailable`: Database not available

---

## Policies

Policy configuration files for media processing rules.

### GET /api/policies

List all policy files from the policies directory.

**Response**: `200 OK`

```json
{
  "policies": [
    {
      "name": "default",
      "filename": "default.yaml",
      "file_path": "/home/user/.vpo/policies/default.yaml",
      "last_modified": "2025-01-15T10:00:00+00:00",
      "schema_version": 12,
      "audio_languages": "eng",
      "subtitle_languages": "eng",
      "has_transcode": false,
      "has_transcription": true,
      "is_default": true,
      "parse_error": null
    }
  ],
  "total": 3,
  "policies_directory": "/home/user/.vpo/policies",
  "default_policy_path": "/home/user/.vpo/policies/default.yaml",
  "default_policy_missing": false,
  "directory_exists": true
}
```

**Errors**:

- `503 Service Unavailable`: Service shutting down

---

### GET /api/policies/{name}

Get detailed policy configuration for editing.

**Path Parameters**:

| Name | Type | Description |
|------|------|-------------|
| `name` | string | Policy name (alphanumeric, dash, underscore) |

**Response**: `200 OK`

```json
{
  "name": "default",
  "filename": "default.yaml",
  "file_path": "/home/user/.vpo/policies/default.yaml",
  "last_modified": "2025-01-15T10:00:00+00:00",
  "schema_version": 12,
  "track_order": ["video", "audio_main", "audio_alternate", "subtitle_main"],
  "audio_language_preference": ["eng", "jpn"],
  "subtitle_language_preference": ["eng"],
  "commentary_patterns": ["commentary", "director"],
  "default_flags": {
    "set_first_video_default": true,
    "set_preferred_audio_default": true,
    "set_preferred_subtitle_default": false,
    "clear_other_defaults": true
  },
  "transcode": null,
  "transcription": {"enabled": true},
  "parse_error": null
}
```

**Errors**:

- `400 Bad Request`: Invalid policy name format or parse error
- `404 Not Found`: Policy not found
- `503 Service Unavailable`: Service shutting down

---

### PUT /api/policies/{name}

Update a policy configuration. Requires CSRF token.

**Path Parameters**:

| Name | Type | Description |
|------|------|-------------|
| `name` | string | Policy name |

**Headers**:

| Name | Required | Description |
|------|----------|-------------|
| `X-CSRF-Token` | Yes | CSRF token from page context |
| `Content-Type` | Yes | Must be `application/json` |

**Request Body**:

```json
{
  "last_modified_timestamp": "2025-01-15T10:00:00+00:00",
  "track_order": ["video", "audio_main", "subtitle_main"],
  "audio_language_preference": ["eng"],
  "subtitle_language_preference": ["eng"],
  "commentary_patterns": ["commentary"],
  "default_flags": {
    "set_first_video_default": true,
    "set_preferred_audio_default": true,
    "set_preferred_subtitle_default": false,
    "clear_other_defaults": true
  }
}
```

**Response**: `200 OK`

```json
{
  "success": true,
  "changed_fields": [
    {
      "field": "audio_language_preference",
      "change_type": "modified",
      "details": "Changed from [\"eng\", \"jpn\"] to [\"eng\"]"
    }
  ],
  "changed_fields_summary": "Modified: audio_language_preference",
  "policy": {
    "name": "default",
    "last_modified": "2025-01-15T10:05:00+00:00"
  }
}
```

**Errors**:

- `400 Bad Request`: Invalid request or validation errors
- `404 Not Found`: Policy not found
- `409 Conflict`: Concurrent modification detected
- `503 Service Unavailable`: Service shutting down

---

### POST /api/policies/{name}/validate

Validate policy configuration without saving (dry-run).

**Path Parameters**:

| Name | Type | Description |
|------|------|-------------|
| `name` | string | Policy name |

**Headers**:

| Name | Required | Description |
|------|----------|-------------|
| `X-CSRF-Token` | Yes | CSRF token from page context |
| `Content-Type` | Yes | Must be `application/json` |

**Request Body**: Same as PUT /api/policies/{name}

**Response**: `200 OK`

```json
{
  "valid": true,
  "errors": [],
  "message": "Policy configuration is valid"
}
```

Or with validation errors:

```json
{
  "valid": false,
  "errors": [
    {
      "field": "audio_language_preference",
      "message": "Invalid language code: 'xyz'",
      "code": "invalid_language_code"
    }
  ],
  "message": "1 validation error(s) found"
}
```

**Errors**:

- `400 Bad Request`: Invalid request format
- `503 Service Unavailable`: Service shutting down

---

## Plans

Pending action plans awaiting approval or rejection.

### GET /api/plans

List plans with optional filters.

**Query Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `status` | string | No | Filter by status: `pending`, `approved`, `rejected`, `applied`, `canceled` |
| `since` | string | No | Time filter: `24h`, `7d`, `30d` |
| `policy_name` | string | No | Filter by policy name |
| `limit` | integer | No | Page size (1-100, default 50) |
| `offset` | integer | No | Pagination offset (default 0) |

**Response**: `200 OK`

```json
{
  "plans": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "id_short": "660e8400",
      "file_id": 123,
      "file_path": "/media/movies/Movie.2024.mkv",
      "filename": "Movie.2024.mkv",
      "policy_name": "default",
      "status": "pending",
      "created_at": "2025-01-15T10:00:00+00:00",
      "updated_at": "2025-01-15T10:00:00+00:00",
      "actions_count": 3,
      "actions_preview": "Reorder tracks, Set defaults, Update metadata",
      "file_exists": true
    }
  ],
  "total": 10,
  "limit": 50,
  "offset": 0,
  "has_filters": false
}
```

**Errors**:

- `400 Bad Request`: Invalid parameter value
- `503 Service Unavailable`: Database not available

---

### POST /api/plans/{plan_id}/approve

Approve a pending plan and create an execution job.

**Path Parameters**:

| Name | Type | Description |
|------|------|-------------|
| `plan_id` | string (UUID) | Plan identifier |

**Headers**:

| Name | Required | Description |
|------|----------|-------------|
| `X-CSRF-Token` | Yes | CSRF token from page context |

**Response**: `200 OK`

```json
{
  "success": true,
  "plan": {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "status": "approved"
  },
  "job_id": "770e8400-e29b-41d4-a716-446655440002",
  "job_url": "/jobs/770e8400-e29b-41d4-a716-446655440002",
  "warning": null
}
```

**Errors**:

- `400 Bad Request`: Invalid plan ID format
- `404 Not Found`: Plan not found
- `409 Conflict`: Plan is not in pending status
- `503 Service Unavailable`: Database not available

---

### POST /api/plans/{plan_id}/reject

Reject a pending plan.

**Path Parameters**:

| Name | Type | Description |
|------|------|-------------|
| `plan_id` | string (UUID) | Plan identifier |

**Headers**:

| Name | Required | Description |
|------|----------|-------------|
| `X-CSRF-Token` | Yes | CSRF token from page context |

**Response**: `200 OK`

```json
{
  "success": true,
  "plan": {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "status": "rejected"
  }
}
```

**Errors**:

- `400 Bad Request`: Invalid plan ID format
- `404 Not Found`: Plan not found
- `409 Conflict`: Plan is not in pending status
- `503 Service Unavailable`: Database not available

---

## Common Response Patterns

### Pagination Response

All list endpoints return paginated data with consistent structure:

```json
{
  "{resource}": [...],
  "total": 150,
  "limit": 50,
  "offset": 0,
  "has_filters": false
}
```

Where `{resource}` is `jobs`, `files`, `plans`, `policies`, or `transcriptions`.

### Error Response

All error responses follow this structure:

```json
{
  "error": "Human-readable error message",
  "details": "Optional additional context"
}
```

### Validation Error Response

Validation failures include structured error details:

```json
{
  "error": "Validation failed",
  "errors": [
    {
      "field": "field_name",
      "message": "Description of the validation error",
      "code": "error_code"
    }
  ],
  "details": "2 validation error(s) found"
}
```

---

## CSRF Protection

State-changing operations (POST, PUT, DELETE) require a CSRF token:

1. **Obtain the token**: The token is embedded in HTML pages as `csrf_token` in the template context
2. **Include in requests**: Send the token in the `X-CSRF-Token` header

**Example**:

```javascript
fetch('/api/policies/default', {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRF-Token': csrfToken
  },
  body: JSON.stringify(policyData)
});
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `400` | Bad Request - Invalid parameters or request body |
| `404` | Not Found - Resource does not exist |
| `409` | Conflict - Concurrent modification or invalid state transition |
| `503` | Service Unavailable - Database not available or service shutting down |

### Common Error Scenarios

**400 Bad Request**:
- Invalid UUID format for job/plan IDs
- Invalid integer format for file/transcription IDs
- Invalid enum value for status/type filters
- Malformed JSON in request body

**404 Not Found**:
- Job, file, transcription, policy, or plan does not exist

**409 Conflict**:
- Policy file was modified by another process (concurrent modification)
- Plan is not in `pending` status when attempting approve/reject

**503 Service Unavailable**:
- Database connection pool not available
- Service is shutting down

---

## Authentication

See [Authentication Guide](usage/authentication.md) for details on configuring authentication when the Web UI is exposed beyond localhost.

---

## Related docs

- [CLI Usage](usage/cli-usage.md) - Command-line interface reference
- [Daemon Mode](daemon-mode.md) - Running VPO as a daemon
- [Policy Editor](usage/policy-editor.md) - Visual policy editing guide
- [Database Design](design/design-database.md) - Database schema details
- [Glossary](glossary.md) - Term definitions
