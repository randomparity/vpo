# Existing API Contracts

**Feature**: 017-live-job-polling
**Date**: 2025-11-23

## Overview

This feature uses existing API endpoints for polling. No new endpoints are required for core functionality. This document captures the existing contracts that polling will rely on.

## Endpoints Used by Polling

### GET /api/jobs

List jobs with filtering and pagination.

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| status | string | - | Filter by status: queued, running, completed, failed, cancelled |
| type | string | - | Filter by job type: scan, apply, transcode, move |
| since | string | - | Time filter: 24h, 7d |
| limit | int | 50 | Page size (1-100) |
| offset | int | 0 | Pagination offset |

**Response** (200 OK):
```json
{
  "jobs": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "job_type": "scan",
      "status": "running",
      "file_path": "/media/videos",
      "progress_percent": 45,
      "created_at": "2025-11-23T10:30:00Z",
      "completed_at": null,
      "duration_seconds": null
    }
  ],
  "total": 125,
  "limit": 50,
  "offset": 0,
  "has_filters": false
}
```

**Error Responses**:
- 400 Bad Request: Invalid filter values
- 503 Service Unavailable: Database not available or shutting down

**Polling Notes**:
- Same query parameters used for each poll to maintain filter state
- Compare `jobs` array with cached data to detect changes
- `total` may change between polls (new jobs added)

---

### GET /api/jobs/{job_id}

Get detailed job information.

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| job_id | string (UUID) | Job identifier |

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "id_short": "550e8400",
  "job_type": "scan",
  "status": "running",
  "priority": 5,
  "file_path": "/media/videos",
  "policy_name": null,
  "created_at": "2025-11-23T10:30:00Z",
  "started_at": "2025-11-23T10:30:01Z",
  "completed_at": null,
  "duration_seconds": null,
  "progress_percent": 45,
  "error_message": null,
  "output_path": null,
  "summary": "Scanning /media/videos",
  "summary_raw": {"files_scanned": 45, "total_files": 100},
  "has_logs": true
}
```

**Error Responses**:
- 400 Bad Request: Invalid job ID format
- 404 Not Found: Job does not exist
- 503 Service Unavailable: Database not available or shutting down

**Polling Notes**:
- Poll this endpoint for real-time progress updates
- Check `status` field for terminal states (completed, failed, cancelled)
- Stop polling when job reaches terminal state
- Handle 404 gracefully (job may be deleted)

---

### GET /api/jobs/{job_id}/logs

Get job log content with pagination.

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| job_id | string (UUID) | Job identifier |

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| lines | int | 500 | Number of lines to return (max 1000) |
| offset | int | 0 | Line offset from start |

**Response** (200 OK):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "lines": [
    "2025-11-23 10:30:01 INFO Starting scan...",
    "2025-11-23 10:30:02 INFO Processing file 1/100"
  ],
  "total_lines": 250,
  "offset": 0,
  "has_more": true
}
```

**Error Responses**:
- 400 Bad Request: Invalid job ID format
- 503 Service Unavailable: Shutting down

**Polling Notes**:
- Use longer polling interval (15s) for logs
- Only poll logs when job is in `running` state
- Track `total_lines` to detect new log entries
- Fetch only new lines by using appropriate offset

---

## Optional Enhancement: Polling Config Endpoint

A new endpoint could be added to dynamically provide polling configuration:

### GET /api/config/polling

Get polling configuration.

**Response** (200 OK):
```json
{
  "interval_ms": 5000,
  "enabled": true,
  "log_interval_ms": 15000
}
```

**Note**: For initial implementation, config is embedded in HTML templates via data attributes. This endpoint is optional for future flexibility.

---

## Response Headers

All API responses include standard headers:
- `Content-Type: application/json`
- `Cache-Control: no-cache` (for polling endpoints)

No additional headers required for polling support.

## Rate Limiting

No server-side rate limiting currently implemented. Client-side polling interval (min 2s) and backoff provide natural throttling.

Future consideration: Add rate limiting if server load becomes a concern.
