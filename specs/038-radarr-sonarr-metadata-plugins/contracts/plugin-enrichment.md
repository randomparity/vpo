# Plugin Enrichment Contract

**Version**: 1.0.0
**Plugin API Version**: 1.0.0

## Overview

This document defines the contract between the Radarr/Sonarr metadata plugins and the VPO core system. The plugins implement the `AnalyzerPlugin` protocol and return enrichment data via the `on_file_scanned` event handler.

## Plugin Interface

### Required Attributes

```python
class RadarrMetadataPlugin:
    name: str = "radarr-metadata"
    version: str = "1.0.0"
    events: list[str] = ["file.scanned"]

class SonarrMetadataPlugin:
    name: str = "sonarr-metadata"
    version: str = "1.0.0"
    events: list[str] = ["file.scanned"]
```

### Event Handler

```python
def on_file_scanned(self, event: FileScannedEvent) -> dict[str, Any] | None:
    """Called after a file is scanned.

    Args:
        event: FileScannedEvent with file_info and tracks.

    Returns:
        Optional dict of enriched metadata to merge into file_info,
        or None if no enrichment available.
    """
```

## Enrichment Data Schema

### Movie Enrichment (Radarr)

```json
{
  "original_language": "eng",
  "external_source": "radarr",
  "external_id": 123,
  "external_title": "The Matrix",
  "external_year": 1999,
  "imdb_id": "tt0133093",
  "tmdb_id": 603
}
```

### TV Episode Enrichment (Sonarr)

```json
{
  "original_language": "eng",
  "external_source": "sonarr",
  "external_id": 1,
  "external_title": "Breaking Bad",
  "external_year": 2008,
  "series_title": "Breaking Bad",
  "season_number": 1,
  "episode_number": 1,
  "episode_title": "Pilot",
  "imdb_id": "tt0903747",
  "tvdb_id": 81189
}
```

## Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| original_language | string? | Yes* | ISO 639-2/B language code (e.g., "eng", "jpn") |
| external_source | string | Yes | "radarr" or "sonarr" |
| external_id | int | Yes | Movie ID (Radarr) or Series ID (Sonarr) |
| external_title | string | Yes | Title from external service |
| external_year | int? | No | Release year |
| series_title | string? | No | Series title (Sonarr only) |
| season_number | int? | No | Season number (Sonarr only) |
| episode_number | int? | No | Episode number (Sonarr only) |
| episode_title | string? | No | Episode title (Sonarr only) |
| imdb_id | string? | No | IMDb identifier |
| tmdb_id | int? | No | TMDb identifier (Radarr only) |
| tvdb_id | int? | No | TVDb identifier (Sonarr only) |

*original_language is null if not available from external service

## Language Code Normalization

The plugin MUST normalize language names to ISO 639-2/B codes:

| Input (API) | Output (VPO) |
|-------------|--------------|
| "English" | "eng" |
| "French" | "fra" |
| "German" | "deu" |
| "Spanish" | "spa" |
| "Italian" | "ita" |
| "Japanese" | "jpn" |
| "Korean" | "kor" |
| "Chinese" | "zho" |
| "Portuguese" | "por" |
| "Russian" | "rus" |
| (unknown) | null |

Use `video_policy_orchestrator.language.normalize_language()` for conversion.

## Error Handling Contract

### Plugin Behavior on Error

| Error Type | Behavior |
|------------|----------|
| Connection refused | Return None, log warning |
| Timeout | Return None, log warning |
| Auth failure (401) | Return None, log error, disable for session |
| Rate limited (429) | Retry once after 1s delay, then return None |
| Server error (5xx) | Return None, log warning |
| Parse error | Return None, log error with details |
| No match found | Return None (normal case, log at debug) |

### Plugin MUST NOT

- Raise exceptions (catch all and return None)
- Block for more than 30 seconds
- Modify the FileScannedEvent
- Make network calls outside configured endpoints

## Configuration Contract

### Expected Configuration Section

```toml
[plugins.radarr]
enabled = true
url = "http://localhost:7878"
api_key = "your-api-key-here"  # pragma: allowlist secret

[plugins.sonarr]
enabled = true
url = "http://localhost:8989"
api_key = "your-api-key-here"  # pragma: allowlist secret
```

### Configuration Validation

Plugin initialization MUST:
1. Validate URL format (http:// or https://)
2. Validate API key is non-empty
3. Test connection to `/api/v3/system/status`
4. Log connection success/failure

## Policy Integration

### Accessing Enrichment Data

After plugin enrichment, the data is available in FileInfo:

```python
# In policy evaluation
file_info = event.file_info
original_language = file_info.get("original_language")  # "eng" or None
external_source = file_info.get("external_source")      # "radarr"/"sonarr" or None
```

### Policy Condition Example

```yaml
# Policy using enriched original_language
video:
  - when:
      original_language_is: jpn
      video_language_is: und
    then:
      set_language: jpn
```

## Versioning

### Plugin Version

Follows semantic versioning:
- MAJOR: Breaking changes to enrichment schema
- MINOR: New optional fields added
- PATCH: Bug fixes, no schema changes

### Compatibility

- Plugin API version 1.x compatible with VPO plugin system 1.x
- Enrichment schema backward compatible within major version
