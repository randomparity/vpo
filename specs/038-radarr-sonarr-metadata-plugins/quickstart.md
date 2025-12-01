# Quickstart: Radarr and Sonarr Metadata Plugins

**Feature**: 038-radarr-sonarr-metadata-plugins

## Overview

This guide covers the implementation of metadata enrichment plugins for Radarr (movies) and Sonarr (TV series). These plugins connect to existing Radarr/Sonarr installations to fetch metadata, particularly original language, for video files during VPO scans.

## Prerequisites

- VPO installed and configured
- Running Radarr and/or Sonarr instance(s)
- API keys for each service (found in Settings > General > Security)
- Files accessible at identical paths from both VPO and Radarr/Sonarr

## Quick Configuration

Add to your VPO config (`~/.vpo/config.toml`):

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

## Directory Structure

```
src/video_policy_orchestrator/
├── plugins/
│   ├── radarr_metadata/
│   │   ├── __init__.py
│   │   ├── plugin.py          # RadarrMetadataPlugin class
│   │   ├── client.py          # Radarr API client
│   │   └── models.py          # Radarr-specific dataclasses
│   └── sonarr_metadata/
│       ├── __init__.py
│       ├── plugin.py          # SonarrMetadataPlugin class
│       ├── client.py          # Sonarr API client
│       └── models.py          # Sonarr-specific dataclasses
├── config/
│   └── models.py              # Add MetadataPluginSettings
└── language.py                # Existing - normalize_language()

tests/
├── unit/
│   └── plugins/
│       ├── test_radarr_plugin.py
│       └── test_sonarr_plugin.py
└── integration/
    └── plugins/
        ├── test_radarr_integration.py
        └── test_sonarr_integration.py
```

## Implementation Steps

### Step 1: Add Configuration Models

Extend `config/models.py`:

```python
@dataclass
class PluginConnectionConfig:
    url: str
    api_key: str
    enabled: bool = True
    timeout_seconds: int = 30

@dataclass
class MetadataPluginSettings:
    radarr: PluginConnectionConfig | None = None
    sonarr: PluginConnectionConfig | None = None
```

### Step 2: Implement Radarr Plugin

Create `plugins/radarr_metadata/plugin.py`:

```python
from video_policy_orchestrator.plugin.events import FileScannedEvent
from video_policy_orchestrator.language import normalize_language

class RadarrMetadataPlugin:
    name = "radarr-metadata"
    version = "1.0.0"
    events = ["file.scanned"]

    def __init__(self, config: PluginConnectionConfig):
        self._client = RadarrClient(config)
        self._cache: RadarrCache | None = None

    def on_file_scanned(self, event: FileScannedEvent) -> dict | None:
        # Build cache on first call
        if self._cache is None:
            self._cache = self._client.build_cache()

        # Look up movie by file path
        movie = self._cache.lookup_by_path(str(event.file_path))
        if movie is None:
            return None

        # Return enrichment data
        lang = movie.original_language
        return {
            "original_language": normalize_language(lang.name) if lang else None,
            "external_source": "radarr",
            "external_id": movie.id,
            "external_title": movie.title,
            "external_year": movie.year,
        }
```

### Step 3: Implement Sonarr Plugin

Create `plugins/sonarr_metadata/plugin.py`:

```python
class SonarrMetadataPlugin:
    name = "sonarr-metadata"
    version = "1.0.0"
    events = ["file.scanned"]

    def __init__(self, config: PluginConnectionConfig):
        self._client = SonarrClient(config)
        self._cache = SonarrCache.empty()

    def on_file_scanned(self, event: FileScannedEvent) -> dict | None:
        # Use parse endpoint for efficient lookup
        result = self._client.parse(str(event.file_path))
        if result.series is None:
            return None

        # Cache result
        self._cache.parse_results[str(event.file_path)] = result

        # Return enrichment data
        series = result.series
        episode = result.episodes[0] if result.episodes else None
        lang = series.original_language

        return {
            "original_language": normalize_language(lang.name) if lang else None,
            "external_source": "sonarr",
            "external_id": series.id,
            "external_title": series.title,
            "external_year": series.year,
            "series_title": series.title,
            "season_number": episode.season_number if episode else None,
            "episode_number": episode.episode_number if episode else None,
            "episode_title": episode.title if episode else None,
        }
```

### Step 4: Implement API Clients

Create HTTP clients using aiohttp patterns from VPO codebase:

```python
class RadarrClient:
    def __init__(self, config: PluginConnectionConfig):
        self._base_url = config.url.rstrip("/")
        self._api_key = config.api_key
        self._timeout = config.timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {"X-Api-Key": self._api_key}

    def get_movies(self) -> list[RadarrMovie]:
        # GET /api/v3/movie
        ...

    def get_movie_files(self) -> list[RadarrMovieFile]:
        # GET /api/v3/moviefile
        ...

    def build_cache(self) -> RadarrCache:
        movies = self.get_movies()
        files = self.get_movie_files()
        # Build path -> movie_id index
        ...
```

### Step 5: Register Plugins

Update plugin loader or use entry points:

```python
# Entry point in pyproject.toml
[project.entry-points."vpo.plugins"]
radarr-metadata = "video_policy_orchestrator.plugins.radarr_metadata:RadarrMetadataPlugin"
sonarr-metadata = "video_policy_orchestrator.plugins.sonarr_metadata:SonarrMetadataPlugin"
```

### Step 6: Add Policy Support

To use original_language in policies, update policy evaluation:

```python
# In policy/conditions.py
def evaluate_original_language_condition(
    condition: OriginalLanguageCondition,
    file_info: FileInfo,
) -> bool:
    original = file_info.get("original_language")
    if original is None:
        return False
    return any(languages_match(original, lang) for lang in condition.languages)
```

## Testing

### Unit Tests

```python
def test_radarr_enrichment():
    plugin = RadarrMetadataPlugin(mock_config)
    plugin._cache = RadarrCache(
        movies={1: RadarrMovie(id=1, title="Test", ...)},
        path_to_movie={"/movies/test.mkv": 1},
    )

    event = FileScannedEvent(file_path=Path("/movies/test.mkv"), ...)
    result = plugin.on_file_scanned(event)

    assert result["original_language"] == "eng"
    assert result["external_source"] == "radarr"
```

### Integration Tests

```python
@pytest.mark.integration
def test_radarr_connection():
    client = RadarrClient(test_config)
    status = client.get_status()
    assert status["appName"] == "Radarr"
```

## Policy Usage with Original Language

After files are enriched with metadata from Radarr or Sonarr, the `original_language` field becomes available for use in policy conditions. This allows you to automatically tag video tracks with the correct language based on the content's original language.

### Using original_language in Policies

The enriched metadata is accessible in policy conditions. Here are common use cases:

#### Tag Video Tracks with Original Language

```yaml
# tag-original-language.yaml
schema_version: 10

# When original_language is known and video track is undefined,
# set the video track's language to the original language
video:
  - when:
      original_language_is: jpn
      video_language_is: und
    then:
      set_language: jpn

  - when:
      original_language_is: eng
      video_language_is: und
    then:
      set_language: eng

  - when:
      original_language_is: kor
      video_language_is: und
    then:
      set_language: kor
```

#### Conditional Audio Track Selection Based on Original Language

```yaml
# audio-selection.yaml
schema_version: 10

# Keep original language audio as default, others as secondary
audio:
  - when:
      matches_original_language: true
    then:
      set_default: true
      keep: true

  - when:
      matches_original_language: false
      language_is: [eng, jpn, kor]
    then:
      set_default: false
      keep: true
```

### Available Enrichment Fields

After enrichment, the following fields are available in the file context:

| Field | Type | Description |
|-------|------|-------------|
| `original_language` | string | ISO 639-2/B code (e.g., "eng", "jpn") |
| `external_source` | string | "radarr" or "sonarr" |
| `external_id` | int | Movie/Series ID from external service |
| `external_title` | string | Title from external service |
| `external_year` | int | Release year |
| `series_title` | string | (Sonarr only) Series title |
| `season_number` | int | (Sonarr only) Season number |
| `episode_number` | int | (Sonarr only) Episode number |

## Usage Example

After configuration, scan files normally:

```bash
# Scan with metadata enrichment
vpo scan /movies

# View enriched metadata
vpo inspect /movies/The\ Matrix\ \(1999\)/The\ Matrix.mkv
# Shows: Original Language: English (from Radarr)

# Use in policy
vpo apply --policy tag-original-language.yaml /movies
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Connection refused" | Check Radarr/Sonarr is running and URL is correct |
| "401 Unauthorized" | Verify API key in config |
| "No match found" | Ensure file paths are identical between systems |
| "Timeout" | Increase timeout_seconds or check network |

## Related Documentation

- [Radarr API Contract](contracts/radarr-api.md)
- [Sonarr API Contract](contracts/sonarr-api.md)
- [Plugin Enrichment Contract](contracts/plugin-enrichment.md)
- [Data Model](data-model.md)
- [Research](research.md)
