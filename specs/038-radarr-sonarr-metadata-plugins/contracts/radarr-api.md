# Radarr v3 API Contract

**Version**: v3
**Base URL**: `{configured_url}/api/v3`

## Authentication

All requests require the `X-Api-Key` header:

```
X-Api-Key: {api_key}
```

## Endpoints Used

### GET /system/status

Test API connectivity and authentication.

**Request**:
```http
GET /api/v3/system/status
X-Api-Key: {api_key}
```

**Response** (200 OK):
```json
{
  "appName": "Radarr",
  "version": "5.x.x.x",
  "buildTime": "2024-01-01T00:00:00Z",
  "isDebug": false,
  "isProduction": true,
  "isAdmin": false,
  "isUserInteractive": false,
  "startupPath": "/app",
  "appData": "/config",
  "osName": "debian",
  "osVersion": "11",
  "isNetCore": true,
  "isLinux": true,
  "isOsx": false,
  "isWindows": false,
  "isDocker": true,
  "branch": "master",
  "authentication": "forms",
  "sqliteVersion": "3.39.4",
  "urlBase": ""
}
```

**Error Responses**:
- `401 Unauthorized`: Invalid API key
- `503 Service Unavailable`: Radarr not ready

---

### GET /movie

List all movies in the library.

**Request**:
```http
GET /api/v3/movie
X-Api-Key: {api_key}
```

**Response** (200 OK):
```json
[
  {
    "id": 123,
    "title": "The Matrix",
    "originalTitle": "The Matrix",
    "originalLanguage": {
      "id": 1,
      "name": "English"
    },
    "year": 1999,
    "path": "/movies/The Matrix (1999)",
    "hasFile": true,
    "imdbId": "tt0133093",
    "tmdbId": 603,
    "added": "2020-01-01T00:00:00Z",
    "qualityProfileId": 1,
    "monitored": true
  }
]
```

**Fields Used**:
| Field | Type | Description |
|-------|------|-------------|
| id | int | Unique movie identifier |
| title | string | Display title |
| originalTitle | string? | Original release title |
| originalLanguage | object? | Original language info |
| originalLanguage.id | int | Language ID |
| originalLanguage.name | string | Language name (e.g., "English") |
| year | int | Release year |
| path | string | Movie folder path |
| hasFile | bool | Whether movie file exists |
| imdbId | string? | IMDb identifier |
| tmdbId | int? | TMDb identifier |

---

### GET /moviefile

List all movie files in the library.

**Request**:
```http
GET /api/v3/moviefile
X-Api-Key: {api_key}
```

**Optional Query Parameters**:
- `movieId`: Filter by movie ID

**Response** (200 OK):
```json
[
  {
    "id": 456,
    "movieId": 123,
    "path": "/movies/The Matrix (1999)/The Matrix (1999).mkv",
    "relativePath": "The Matrix (1999).mkv",
    "size": 8589934592,
    "dateAdded": "2020-01-15T00:00:00Z",
    "quality": {
      "quality": {
        "id": 7,
        "name": "Bluray-1080p"
      }
    },
    "mediaInfo": {
      "videoBitrate": 0,
      "videoCodec": "h265",
      "videoDynamicRange": "",
      "videoDynamicRangeType": "",
      "audioChannels": 5.1,
      "audioCodec": "TrueHD Atmos"
    }
  }
]
```

**Fields Used**:
| Field | Type | Description |
|-------|------|-------------|
| id | int | Unique file identifier |
| movieId | int | Associated movie ID |
| path | string | Absolute file path |
| relativePath | string | Path relative to movie folder |
| size | int | File size in bytes |

---

## Error Handling

### Standard Error Response

```json
{
  "message": "Error description",
  "errorMessage": "Detailed error message"
}
```

### HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 400 | Bad Request | Log error, skip |
| 401 | Unauthorized | Disable plugin for session |
| 404 | Not Found | Resource doesn't exist |
| 429 | Too Many Requests | Wait and retry once |
| 500 | Server Error | Log error, skip |
| 503 | Service Unavailable | Log error, skip |

---

## Rate Limiting

Radarr does not explicitly rate limit, but:
- Avoid concurrent requests to same instance
- Implement reasonable delays between bulk requests
- Cache responses to minimize API calls
