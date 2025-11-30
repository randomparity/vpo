# API Contracts: V9 Policy Editor

**Phase 1 Output** | **Date**: 2025-11-30

## Overview

This document defines the REST API contracts for the policy editor. These endpoints are extensions of the existing policy API.

## Base URL

```
/api/policies
```

## Endpoints

### GET /api/policies/{name}

Load a policy for editing.

**Request**

```http
GET /api/policies/default HTTP/1.1
Accept: application/json
```

**Response (200 OK)**

```json
{
  "name": "default",
  "schema_version": 10,
  "last_modified": "2025-11-30T10:30:00Z",
  "track_order": ["video", "audio_main", "audio_alternate", "audio_commentary", "subtitle_main", "subtitle_forced", "subtitle_commentary", "attachment"],
  "audio_language_preference": ["eng", "und"],
  "subtitle_language_preference": ["eng", "und"],
  "commentary_patterns": ["commentary", "director"],
  "default_flags": {
    "set_first_video_default": true,
    "set_preferred_audio_default": true,
    "set_preferred_subtitle_default": false,
    "clear_other_defaults": true,
    "set_subtitle_default_when_audio_differs": false
  },
  "transcription": null,
  "audio_filter": {
    "languages": ["eng", "jpn"],
    "fallback_mode": "keep_all",
    "minimum": 1,
    "keep_music_tracks": true,
    "exclude_music_from_language_filter": true,
    "keep_sfx_tracks": true,
    "exclude_sfx_from_language_filter": true,
    "keep_non_speech_tracks": true,
    "exclude_non_speech_from_language_filter": true
  },
  "subtitle_filter": {
    "languages": ["eng"],
    "preserve_forced": true,
    "remove_all": false
  },
  "attachment_filter": null,
  "container": null,
  "conditional": [
    {
      "name": "Skip anime transcoding",
      "when": {
        "type": "exists",
        "track_type": "audio",
        "filters": {
          "language": "jpn"
        }
      },
      "then_actions": [
        {"type": "skip_video_transcode"},
        {"type": "warn", "message": "Skipping Japanese audio content"}
      ],
      "else_actions": null
    }
  ],
  "audio_synthesis": {
    "tracks": [
      {
        "name": "compatibility_stereo",
        "codec": "aac",
        "channels": "stereo",
        "source_prefer": [
          {"language": "eng"},
          {"channels": "max"}
        ],
        "bitrate": "192k",
        "skip_if_exists": {
          "codec": ["aac", "eac3"],
          "channels": 2
        },
        "title": "inherit",
        "language": "inherit",
        "position": "end"
      }
    ]
  },
  "transcode_v6": {
    "video": {
      "target_codec": "hevc",
      "skip_if": {
        "codec_matches": ["hevc", "h265"],
        "resolution_within": "1080p",
        "bitrate_under": "15M"
      },
      "quality": {
        "mode": "crf",
        "crf": 20,
        "preset": "medium",
        "tune": null,
        "two_pass": false
      },
      "scaling": {
        "max_resolution": "1080p",
        "algorithm": "lanczos",
        "upscale": false
      },
      "hardware_acceleration": {
        "enabled": "auto",
        "fallback_to_cpu": true
      }
    },
    "audio": {
      "preserve_codecs": ["truehd", "dts-hd", "flac"],
      "transcode_to": "aac",
      "transcode_bitrate": "192k"
    }
  },
  "workflow": {
    "phases": ["analyze", "apply", "transcode"],
    "auto_process": false,
    "on_error": "continue"
  }
}
```

**Response (404 Not Found)**

```json
{
  "error": "Policy not found",
  "name": "nonexistent"
}
```

---

### PUT /api/policies/{name}

Save a policy.

**Request**

```http
PUT /api/policies/default HTTP/1.1
Content-Type: application/json
X-Last-Modified: 2025-11-30T10:30:00Z

{
  "schema_version": 10,
  "track_order": ["video", "audio_main", ...],
  ... (complete policy data)
}
```

**Headers**

| Header | Required | Description |
|--------|----------|-------------|
| `X-Last-Modified` | Yes | Timestamp from GET response for optimistic locking |

**Response (200 OK)**

```json
{
  "success": true,
  "name": "default",
  "last_modified": "2025-11-30T11:00:00Z"
}
```

**Response (400 Bad Request)** - Validation Error

```json
{
  "error": "Validation failed",
  "details": [
    {
      "field": "audio_filter.languages",
      "message": "Cannot be empty when audio_filter is enabled"
    },
    {
      "field": "transcode_v6.video.quality.crf",
      "message": "CRF must be between 0 and 51"
    }
  ]
}
```

**Response (409 Conflict)** - Concurrent Modification

```json
{
  "error": "Concurrent modification detected",
  "server_modified": "2025-11-30T10:45:00Z",
  "client_modified": "2025-11-30T10:30:00Z",
  "message": "The policy was modified by another user. Please reload and try again."
}
```

---

### POST /api/policies/{name}/validate

Validate policy data without saving (dry-run).

**Request**

```http
POST /api/policies/default/validate HTTP/1.1
Content-Type: application/json

{
  "schema_version": 10,
  ... (complete policy data)
}
```

**Response (200 OK)** - Valid

```json
{
  "valid": true,
  "warnings": [
    "Container conversion to MP4 may drop PGS subtitles"
  ],
  "yaml_preview": "schema_version: 10\ntrack_order:\n  - video\n  ..."
}
```

**Response (200 OK)** - Invalid

```json
{
  "valid": false,
  "errors": [
    {
      "field": "conditional.0.when.conditions",
      "message": "'and' condition must have at least 2 sub-conditions"
    }
  ],
  "warnings": []
}
```

---

### POST /api/policies

Create a new policy.

**Request**

```http
POST /api/policies HTTP/1.1
Content-Type: application/json

{
  "name": "anime-processing",
  "schema_version": 10,
  "track_order": ["video", "audio_main", ...],
  ... (initial policy data)
}
```

**Response (201 Created)**

```json
{
  "success": true,
  "name": "anime-processing",
  "last_modified": "2025-11-30T11:00:00Z"
}
```

**Response (409 Conflict)** - Policy Exists

```json
{
  "error": "Policy already exists",
  "name": "anime-processing"
}
```

---

### GET /api/policies

List all policies (for policy selection).

**Request**

```http
GET /api/policies HTTP/1.1
Accept: application/json
```

**Response (200 OK)**

```json
{
  "policies": [
    {
      "name": "default",
      "schema_version": 10,
      "last_modified": "2025-11-30T10:30:00Z"
    },
    {
      "name": "anime-processing",
      "schema_version": 9,
      "last_modified": "2025-11-29T15:00:00Z"
    }
  ]
}
```

---

## Error Response Format

All error responses follow this structure:

```json
{
  "error": "Short error description",
  "message": "Detailed error message (optional)",
  "details": [
    {
      "field": "path.to.field",
      "message": "Field-specific error"
    }
  ]
}
```

## HTTP Status Codes

| Code | Meaning | Usage |
|------|---------|-------|
| 200 | OK | Successful GET, PUT, or validation |
| 201 | Created | Successfully created new policy |
| 400 | Bad Request | Validation error |
| 404 | Not Found | Policy does not exist |
| 409 | Conflict | Concurrent modification or policy already exists |
| 500 | Internal Server Error | Unexpected server error |

## Field Path Format

Field paths use dot notation for nested fields:

- `audio_filter.languages` - Array field in audio_filter
- `conditional.0.when.type` - First conditional rule's condition type
- `transcode_v6.video.quality.crf` - Nested field in V6 transcode

Array indices are 0-based integers.

## Content Types

- Request: `application/json`
- Response: `application/json`
- YAML Preview: Returned as string in JSON response

## Rate Limiting

No rate limiting on policy API endpoints.

## Authentication

Policy API follows the server's authentication configuration (if enabled). When authentication is required, include appropriate credentials in the request.
