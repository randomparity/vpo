# Research: Radarr and Sonarr Metadata Plugins

**Date**: 2025-12-01
**Feature**: 038-radarr-sonarr-metadata-plugins

## Executive Summary

This document captures research findings for implementing Radarr and Sonarr metadata plugins for VPO. Both services provide REST APIs that can be used to enrich scanned files with metadata, particularly original language information.

## 1. VPO Plugin Architecture

### Decision: Use AnalyzerPlugin Protocol
**Rationale**: Plugins only need to read metadata from external services and enrich file info. No file modifications are needed.
**Alternatives considered**: MutatorPlugin (rejected - unnecessary complexity for read-only operation)

### Key Patterns from Existing Codebase

| Pattern | Implementation | Location |
|---------|---------------|----------|
| Plugin interface | `AnalyzerPlugin` Protocol | `plugin/interfaces.py` |
| Event subscription | `file.scanned` event | `plugin/events.py` |
| Metadata return | Dict from `on_file_scanned()` | Merged into FileInfo |
| Config storage | Plugin-specific directory | `~/.vpo/plugins/<name>/` |
| HTTP client | aiohttp with asyncio.to_thread() | `server/app.py` |

### Plugin Registration Pattern
```python
class RadarrPlugin:
    name = "radarr-metadata"
    version = "1.0.0"
    events = ["file.scanned"]

    def on_file_scanned(self, event: FileScannedEvent) -> dict[str, Any] | None:
        # Return enrichment dict or None
        return {"original_language": "eng", "radarr_title": "..."}
```

## 2. Radarr v3 API

### Decision: Use full movie list with local path matching
**Rationale**: Radarr v3 API does not support querying by file path. Must retrieve all movies and match locally.
**Alternatives considered**:
- Query by title (rejected - unreliable, requires filename parsing)
- IMDb lookup (rejected - requires external metadata not available)

### Authentication
- **Header**: `X-Api-Key: <api-key>`
- **Alternative**: Query parameter `?apikey=<key>` (not recommended)

### Key Endpoints

| Endpoint | Purpose | Response |
|----------|---------|----------|
| `GET /api/v3/movie` | List all movies | Array of Movie objects |
| `GET /api/v3/moviefile` | List all movie files | Array of MovieFile objects |
| `GET /api/v3/moviefile?movieId={id}` | Files for specific movie | Array of MovieFile objects |

### Movie Object (Relevant Fields)
```json
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
  "tmdbId": 603
}
```

### MovieFile Object (Relevant Fields)
```json
{
  "id": 456,
  "movieId": 123,
  "path": "/movies/The Matrix (1999)/The Matrix (1999).mkv",
  "relativePath": "The Matrix (1999).mkv",
  "size": 8589934592
}
```

### Original Language
- Stored in `movie.originalLanguage.name` (e.g., "English", "French", "Japanese")
- Must be normalized to ISO 639-2/B for VPO (e.g., "eng", "fra", "jpn")

## 3. Sonarr v3 API

### Decision: Use parse endpoint for efficient lookup
**Rationale**: Sonarr provides `/api/v3/parse?path=<filepath>` endpoint that directly identifies series and episodes from a file path. Much more efficient than full list retrieval.
**Alternatives considered**:
- Full episode file list (rejected - inefficient for large libraries)
- Series-by-series lookup (rejected - requires path prefix matching)

### Authentication
- **Header**: `X-Api-Key: <api-key>` (same as Radarr)

### Key Endpoints

| Endpoint | Purpose | Response |
|----------|---------|----------|
| `GET /api/v3/parse?path=<path>` | Parse file path | ParseResult with series/episode |
| `GET /api/v3/series` | List all series | Array of Series objects |
| `GET /api/v3/episodefile?seriesId={id}` | Files for specific series | Array of EpisodeFile objects |

### Parse Result Object
```json
{
  "series": {
    "id": 1,
    "title": "Breaking Bad",
    "path": "/tv/Breaking Bad",
    "languageProfileId": 1
  },
  "episodes": [
    {
      "id": 1,
      "seasonNumber": 1,
      "episodeNumber": 1,
      "title": "Pilot"
    }
  ],
  "episodeInfo": {
    "seasonNumber": 1,
    "episodeNumbers": [1]
  }
}
```

### Series Object (Relevant Fields)
```json
{
  "id": 1,
  "title": "Breaking Bad",
  "year": 2008,
  "path": "/tv/Breaking Bad",
  "imdbId": "tt0903747",
  "tvdbId": 81189,
  "originalLanguage": {
    "id": 1,
    "name": "English"
  }
}
```

### Original Language
- Sonarr v3+ stores `originalLanguage` at series level (similar to Radarr)
- Fallback: Use `languageProfileId` to infer primary language
- Must normalize to ISO 639-2/B for VPO

## 4. Language Code Normalization

### Decision: Create language name to ISO 639-2/B mapping
**Rationale**: Both APIs return language as human-readable names. VPO uses ISO 639-2/B internally.
**Alternatives considered**:
- Use language IDs (rejected - IDs vary between Radarr/Sonarr instances)
- Store both formats (rejected - unnecessary complexity)

### Common Language Mappings
| API Name | ISO 639-2/B |
|----------|-------------|
| English | eng |
| French | fra |
| German | deu |
| Spanish | spa |
| Italian | ita |
| Japanese | jpn |
| Korean | kor |
| Chinese | zho |
| Portuguese | por |
| Russian | rus |

### Implementation
- Use VPO's existing `normalize_language()` function from `video_policy_orchestrator.language`
- Handle unknown languages gracefully (log warning, return None)

## 5. Configuration Storage

### Decision: Store API configuration in VPO config file
**Rationale**: Clarification session confirmed credentials should be in VPO config with filesystem permissions. Consistent with existing VPO patterns.
**Alternatives considered**:
- Environment variables only (rejected - less user-friendly for this use case)
- Plugin-specific config file (rejected - inconsistent with clarification)

### Configuration Structure
```toml
[plugins.radarr]
enabled = true
url = "http://localhost:7878"
api_key = "your-radarr-api-key"  # pragma: allowlist secret

[plugins.sonarr]
enabled = true
url = "http://localhost:8989"
api_key = "your-sonarr-api-key"  # pragma: allowlist secret
```

### Validation on Load
- Validate URL format (must be http:// or https://)
- Test API connection on configuration (call system/status endpoint)
- Cache validation result to avoid repeated checks

## 6. Caching Strategy

### Decision: Session-scoped cache only
**Rationale**: Clarification session confirmed cache should be cleared after scan operation completes. Ensures fresh data on each scan while avoiding redundant API calls within a scan.
**Alternatives considered**:
- Persistent cache with TTL (rejected - stale data risk)
- No caching (rejected - performance impact)

### Implementation
- Build path-to-metadata index on first file scanned
- Radarr: Cache all movies and movie files at scan start
- Sonarr: Cache parse results as files are scanned (lazy loading)
- Clear cache when scan operation completes

## 7. Error Handling Strategy

### Decision: Graceful degradation with logging
**Rationale**: API failures should not block scan operations. Log errors and proceed without enrichment.
**Alternatives considered**:
- Fail fast (rejected - poor user experience for optional enrichment)
- Retry indefinitely (rejected - could hang scans)

### Error Scenarios

| Scenario | Behavior |
|----------|----------|
| Connection timeout | Log warning, skip enrichment, continue scan |
| Invalid API key (401) | Log error, disable plugin for session, continue scan |
| Rate limited (429) | Log warning, wait and retry once, then skip |
| Service unavailable (5xx) | Log warning, skip enrichment, continue scan |
| No match found | Log debug, return None (normal case) |
| Parse error | Log error with details, skip enrichment |

### Timeout Configuration
- Connection timeout: 10 seconds
- Read timeout: 30 seconds (for large libraries)

## 8. File Matching Strategy

### Decision: Exact path matching with identical paths required
**Rationale**: Clarification session confirmed no path mapping support. VPO and Radarr/Sonarr must see identical file paths.
**Alternatives considered**:
- Path mapping configuration (rejected per clarification)
- Filename-only matching (rejected - ambiguous for common filenames)

### Implementation
- Normalize paths (resolve symlinks, normalize separators)
- Compare absolute paths case-sensitively (Linux) or case-insensitively (macOS)
- Log path mismatches at debug level for troubleshooting

## 9. Policy Integration

### Decision: Expose enriched metadata via FileInfo dict
**Rationale**: Plugin enrichment returns dict that merges into FileInfo. Policy conditions can access via standard dict access.
**Alternatives considered**:
- Database schema changes (rejected - unnecessary for initial implementation)
- Separate enrichment table (deferred - may add later for complex queries)

### Enrichment Fields
```python
{
    "original_language": "eng",           # ISO 639-2/B code
    "external_source": "radarr",          # or "sonarr"
    "external_id": 123,                   # Radarr movie ID or Sonarr series ID
    "external_title": "The Matrix",       # Title from external service
    "external_year": 1999,                # Year from external service
    # TV-specific fields (Sonarr only)
    "series_title": "Breaking Bad",
    "season_number": 1,
    "episode_number": 1,
    "episode_title": "Pilot"
}
```

### Policy Condition Usage
```yaml
# Example policy using original_language
video:
  - when:
      original_language_is: jpn
    then:
      set_language: jpn
```

## 10. Outstanding Questions

None - all critical questions resolved through specification and clarification phases.

## References

- [Radarr API Documentation](https://radarr.video/docs/api/)
- [Sonarr API Documentation](https://sonarr.tv/docs/api/)
- VPO Plugin System: `src/video_policy_orchestrator/plugin/`
- VPO Language Utilities: `src/video_policy_orchestrator/language.py`
