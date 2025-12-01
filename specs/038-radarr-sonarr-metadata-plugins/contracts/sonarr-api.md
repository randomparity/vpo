# Sonarr v3 API Contract

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
  "appName": "Sonarr",
  "version": "4.x.x.x",
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
  "branch": "main",
  "authentication": "forms",
  "sqliteVersion": "3.39.4",
  "urlBase": ""
}
```

**Error Responses**:
- `401 Unauthorized`: Invalid API key
- `503 Service Unavailable`: Sonarr not ready

---

### GET /parse

Parse a file path to identify series and episodes. **Primary lookup method**.

**Request**:
```http
GET /api/v3/parse?path={url_encoded_path}
X-Api-Key: {api_key}
```

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| path | string | Yes | URL-encoded absolute file path |

**Response** (200 OK) - Match Found:
```json
{
  "title": "Breaking Bad - S01E01 - Pilot",
  "parsedEpisodeInfo": {
    "releaseTitle": "Breaking Bad - S01E01 - Pilot",
    "seriesTitle": "Breaking Bad",
    "seriesTitleInfo": {
      "title": "Breaking Bad",
      "year": 0
    },
    "quality": {
      "quality": {
        "id": 7,
        "name": "HDTV-720p"
      }
    },
    "seasonNumber": 1,
    "episodeNumbers": [1],
    "isPartialSeason": false,
    "isMultiSeason": false,
    "isSeasonExtra": false,
    "special": false,
    "releaseGroup": "",
    "releaseHash": "",
    "isDaily": false,
    "isAbsoluteNumbering": false
  },
  "series": {
    "id": 1,
    "title": "Breaking Bad",
    "sortTitle": "breaking bad",
    "status": "ended",
    "overview": "A chemistry teacher diagnosed with...",
    "year": 2008,
    "path": "/tv/Breaking Bad",
    "qualityProfileId": 1,
    "languageProfileId": 1,
    "seasonFolder": true,
    "monitored": true,
    "useSceneNumbering": false,
    "runtime": 47,
    "tvdbId": 81189,
    "tvMazeId": 169,
    "imdbId": "tt0903747",
    "firstAired": "2008-01-20",
    "seriesType": "standard",
    "cleanTitle": "breakingbad",
    "added": "2020-01-01T00:00:00Z",
    "originalLanguage": {
      "id": 1,
      "name": "English"
    }
  },
  "episodes": [
    {
      "id": 1,
      "seriesId": 1,
      "tvdbId": 349232,
      "episodeFileId": 1,
      "seasonNumber": 1,
      "episodeNumber": 1,
      "title": "Pilot",
      "airDate": "2008-01-20",
      "airDateUtc": "2008-01-21T02:00:00Z",
      "overview": "Diagnosed with terminal lung cancer...",
      "hasFile": true,
      "monitored": true,
      "absoluteEpisodeNumber": 1
    }
  ]
}
```

**Response** (200 OK) - No Match:
```json
{
  "title": "unknown file",
  "parsedEpisodeInfo": null,
  "series": null,
  "episodes": []
}
```

**Fields Used**:
| Field | Type | Description |
|-------|------|-------------|
| series | object? | Matched series or null |
| series.id | int | Series identifier |
| series.title | string | Series title |
| series.year | int | First air year |
| series.path | string | Series folder path |
| series.originalLanguage | object? | Original language info |
| series.imdbId | string? | IMDb identifier |
| series.tvdbId | int? | TVDb identifier |
| episodes | array | Matched episodes |
| episodes[].seasonNumber | int | Season number |
| episodes[].episodeNumber | int | Episode number |
| episodes[].title | string | Episode title |

---

### GET /series

List all series in the library. **Fallback if parse fails**.

**Request**:
```http
GET /api/v3/series
X-Api-Key: {api_key}
```

**Response** (200 OK):
```json
[
  {
    "id": 1,
    "title": "Breaking Bad",
    "year": 2008,
    "path": "/tv/Breaking Bad",
    "originalLanguage": {
      "id": 1,
      "name": "English"
    },
    "imdbId": "tt0903747",
    "tvdbId": 81189,
    "status": "ended",
    "monitored": true
  }
]
```

---

### GET /episodefile

List episode files. **Fallback for path matching**.

**Request**:
```http
GET /api/v3/episodefile?seriesId={series_id}
X-Api-Key: {api_key}
```

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| seriesId | int | No | Filter by series ID |

**Response** (200 OK):
```json
[
  {
    "id": 1,
    "seriesId": 1,
    "seasonNumber": 1,
    "path": "/tv/Breaking Bad/Season 01/Breaking Bad - S01E01 - Pilot.mkv",
    "relativePath": "Season 01/Breaking Bad - S01E01 - Pilot.mkv",
    "size": 2183157756,
    "dateAdded": "2020-01-15T00:00:00Z",
    "language": {
      "id": 1,
      "name": "English"
    },
    "quality": {
      "quality": {
        "id": 7,
        "name": "HDTV-720p"
      }
    },
    "mediaInfo": {
      "videoBitrate": 0,
      "videoCodec": "h264",
      "audioChannels": 2.0,
      "audioCodec": "AAC"
    }
  }
]
```

**Fields Used**:
| Field | Type | Description |
|-------|------|-------------|
| id | int | File identifier |
| seriesId | int | Associated series ID |
| seasonNumber | int | Season number |
| path | string | Absolute file path |
| language | object? | File language (detected) |

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

## Lookup Strategy

### Primary Strategy (Parse Endpoint)

1. For each scanned file, call `GET /parse?path={file_path}`
2. If `series` is not null, match found
3. Extract `originalLanguage` from series object
4. Cache result for session

### Fallback Strategy (Full List)

If parse fails or returns inconsistent results:

1. Call `GET /series` to get all series
2. Call `GET /episodefile?seriesId={id}` for each series
3. Build path-to-series index
4. Match files by path

---

## Rate Limiting

Sonarr does not explicitly rate limit, but:
- Parse endpoint is designed for single lookups
- Avoid parallel parse requests to same instance
- Cache parse results to minimize API calls
- Consider batching for large scans (use series list instead)
