# Data Model: Radarr and Sonarr Metadata Plugins

**Date**: 2025-12-01
**Feature**: 038-radarr-sonarr-metadata-plugins

## Overview

This document defines the data models for the Radarr and Sonarr metadata plugins. The design follows VPO's existing patterns for plugin enrichment, using typed dataclasses for internal representation and dict-based enrichment returns.

## 1. Configuration Models

### PluginConnectionConfig

Represents connection configuration for an external metadata service.

```python
@dataclass(frozen=True)
class PluginConnectionConfig:
    """Configuration for connecting to Radarr or Sonarr."""

    url: str                    # Base URL (e.g., "http://localhost:7878")
    api_key: str                # API key for authentication
    enabled: bool = True        # Whether plugin is enabled
    timeout_seconds: int = 30   # Request timeout

    # Validation rules:
    # - url: Must start with http:// or https://
    # - api_key: Non-empty string
    # - timeout_seconds: 1-300 range
```

### MetadataPluginSettings

Aggregate settings for all metadata plugins in VPO config.

```python
@dataclass
class MetadataPluginSettings:
    """Settings for all metadata enrichment plugins."""

    radarr: PluginConnectionConfig | None = None
    sonarr: PluginConnectionConfig | None = None
```

## 2. API Response Models

### Radarr Models

```python
@dataclass(frozen=True)
class RadarrLanguage:
    """Language object from Radarr API."""

    id: int
    name: str  # e.g., "English", "French"


@dataclass(frozen=True)
class RadarrMovie:
    """Movie object from Radarr API (subset of fields)."""

    id: int
    title: str
    original_title: str | None
    original_language: RadarrLanguage | None
    year: int
    path: str                    # Movie folder path
    has_file: bool
    imdb_id: str | None
    tmdb_id: int | None
    # Release dates
    digital_release: str | None  # digitalRelease from API
    physical_release: str | None # physicalRelease from API
    cinema_release: str | None   # inCinemas from API
    # v1.1.0 fields
    certification: str | None    # Content rating (PG-13, R, etc.)
    genres: str | None           # Comma-separated genre list
    runtime: int | None          # Runtime in minutes
    status: str | None           # announced/inCinemas/released/deleted
    collection_name: str | None  # From collection.name
    studio: str | None           # Studio name
    rating_tmdb: float | None    # TMDb rating value
    rating_imdb: float | None    # IMDb rating value
    popularity: float | None     # Popularity score
    monitored: bool | None       # Radarr monitoring status
    tags: str | None             # Comma-separated resolved tag names


@dataclass(frozen=True)
class RadarrMovieFile:
    """Movie file object from Radarr API."""

    id: int
    movie_id: int
    path: str                    # Full file path
    relative_path: str
    size: int                    # Size in bytes
    # v1.1.0 fields
    edition: str | None          # Director's Cut, Extended, etc.
    release_group: str | None    # Release group identifier
    scene_name: str | None       # Scene release name
```

### Sonarr Models

```python
@dataclass(frozen=True)
class SonarrLanguage:
    """Language object from Sonarr API."""

    id: int
    name: str  # e.g., "English", "Japanese"


@dataclass(frozen=True)
class SonarrSeries:
    """Series object from Sonarr API (subset of fields)."""

    id: int
    title: str
    year: int
    path: str                    # Series folder path
    original_language: SonarrLanguage | None
    imdb_id: str | None
    tvdb_id: int | None
    first_aired: str | None      # Series premiere date
    # v1.1.0 fields
    certification: str | None    # Content rating (TV-MA, etc.)
    genres: str | None           # Comma-separated genre list
    network: str | None          # TV network (HBO, Netflix, etc.)
    series_type: str | None      # standard/daily/anime
    runtime: int | None          # Episode runtime in minutes
    status: str | None           # continuing/ended/upcoming/deleted
    tvmaze_id: int | None        # TVMaze identifier
    season_count: int | None     # Number of seasons
    total_episode_count: int | None  # Total episode count
    monitored: bool | None       # Sonarr monitoring status
    tags: str | None             # Comma-separated resolved tag names


@dataclass(frozen=True)
class SonarrEpisode:
    """Episode object from Sonarr API."""

    id: int
    series_id: int
    season_number: int
    episode_number: int
    title: str
    has_file: bool
    air_date: str | None         # Episode air date
    # v1.1.0 fields
    absolute_episode_number: int | None  # Absolute episode number (anime)


@dataclass(frozen=True)
class SonarrParseResult:
    """Result from Sonarr parse endpoint."""

    series: SonarrSeries | None
    episodes: tuple[SonarrEpisode, ...]
    # Parse may fail to identify file
```

## 3. Enrichment Models

### MetadataEnrichment

Represents enrichment data returned by plugins to be merged into FileInfo.

```python
@dataclass(frozen=True)
class MetadataEnrichment:
    """Enrichment data from external metadata service."""

    original_language: str | None    # ISO 639-2/B code (e.g., "eng")
    external_source: str             # "radarr" or "sonarr"
    external_id: int                 # Movie ID or Series ID
    external_title: str              # Title from external service
    external_year: int | None        # Year from external service

    # External identifiers
    imdb_id: str | None = None
    tmdb_id: int | None = None

    # TV-specific fields (Sonarr only)
    series_title: str | None = None
    season_number: int | None = None
    episode_number: int | None = None
    episode_title: str | None = None
    tvdb_id: int | None = None

    # Release date fields
    release_date: str | None = None
    cinema_release: str | None = None
    digital_release: str | None = None
    physical_release: str | None = None
    air_date: str | None = None
    premiere_date: str | None = None

    # v1.1.0 common fields
    original_title: str | None = None
    certification: str | None = None
    genres: str | None = None
    runtime: int | None = None
    status: str | None = None
    monitored: bool | None = None
    tags: str | None = None
    popularity: float | None = None

    # v1.1.0 movie fields (Radarr)
    collection_name: str | None = None
    studio: str | None = None
    rating_tmdb: float | None = None
    rating_imdb: float | None = None
    edition: str | None = None
    release_group: str | None = None
    scene_name: str | None = None

    # v1.1.0 TV fields (Sonarr)
    network: str | None = None
    series_type: str | None = None
    tvmaze_id: int | None = None
    season_count: int | None = None
    total_episode_count: int | None = None
    absolute_episode_number: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for plugin return value.

        Required fields always included. Optional fields only when non-None.
        """
        ...
```

### MatchResult

Represents the outcome of matching a file to an external service.

```python
from enum import Enum

class MatchStatus(Enum):
    """Status of file matching attempt."""

    MATCHED = "matched"          # Successfully matched
    UNMATCHED = "unmatched"      # No match found
    UNCERTAIN = "uncertain"      # Multiple possible matches
    ERROR = "error"              # Error during matching


@dataclass(frozen=True)
class MatchResult:
    """Result of attempting to match a file to external service."""

    status: MatchStatus
    enrichment: MetadataEnrichment | None = None
    error_message: str | None = None
    candidates: tuple[int, ...] = ()  # IDs of potential matches if uncertain
```

## 4. Cache Models

### MovieCache (Radarr)

```python
@dataclass
class RadarrCache:
    """Session cache for Radarr API data."""

    movies: dict[int, RadarrMovie]           # movie_id -> movie
    files: dict[str, RadarrMovieFile]        # file_path -> file
    path_to_movie: dict[str, int]            # file_path -> movie_id
    tags: dict[int, str]                     # tag_id -> tag_label

    @classmethod
    def empty(cls) -> "RadarrCache":
        return cls(movies={}, files={}, path_to_movie={}, tags={})

    def lookup_by_path(self, path: str) -> RadarrMovie | None:
        """Look up movie by file path."""
        movie_id = self.path_to_movie.get(path)
        if movie_id is None:
            return None
        return self.movies.get(movie_id)

    def lookup_file_by_path(self, path: str) -> RadarrMovieFile | None:
        """Look up movie file by normalized file path."""
        return self.files.get(path)
```

### SeriesCache (Sonarr)

```python
@dataclass
class SonarrCache:
    """Session cache for Sonarr API data."""

    series: dict[int, SonarrSeries]              # series_id -> series
    parse_results: dict[str, SonarrParseResult]  # file_path -> parse result

    @classmethod
    def empty(cls) -> "SonarrCache":
        return cls(series={}, parse_results={})

    def lookup_by_path(self, path: str) -> SonarrParseResult | None:
        """Look up cached parse result by file path."""
        return self.parse_results.get(path)
```

## 5. Entity Relationships

```
┌─────────────────┐     ┌──────────────────┐
│ VPO FileInfo    │────▶│ MetadataEnrich-  │
│                 │     │ ment (dict)      │
│ - path          │     │                  │
│ - tracks[]      │     │ - original_lang  │
│ - container     │     │ - external_src   │
│ - ...           │     │ - external_id    │
└─────────────────┘     │ - external_title │
                        │ - (tv fields)    │
                        └──────────────────┘
                                │
                 ┌──────────────┴──────────────┐
                 ▼                             ▼
       ┌─────────────────┐           ┌─────────────────┐
       │ RadarrMovie     │           │ SonarrSeries    │
       │                 │           │                 │
       │ - id            │           │ - id            │
       │ - title         │           │ - title         │
       │ - orig_language │           │ - orig_language │
       │ - year          │           │ - year          │
       │ - path          │           │ - path          │
       └────────┬────────┘           └────────┬────────┘
                │                             │
                ▼                             ▼
       ┌─────────────────┐           ┌─────────────────┐
       │ RadarrMovieFile │           │ SonarrEpisode   │
       │                 │           │                 │
       │ - id            │           │ - id            │
       │ - movie_id      │           │ - series_id     │
       │ - path          │           │ - season_num    │
       └─────────────────┘           │ - episode_num   │
                                     └─────────────────┘
```

## 6. State Transitions

### Plugin Lifecycle

```
                    ┌──────────┐
                    │ DISABLED │
                    └────┬─────┘
                         │ enable (config present)
                         ▼
                    ┌──────────┐
         ┌─────────│  INIT    │
         │         └────┬─────┘
         │              │ validate connection
         │              ▼
         │         ┌──────────┐
         │ fail    │  READY   │◀────────────┐
         │         └────┬─────┘             │
         │              │ on_file_scanned   │
         │              ▼                   │
         │         ┌──────────┐             │
         │         │ ENRICHING│─────────────┘
         │         └────┬─────┘   success/not found
         │              │ error
         ▼              ▼
    ┌──────────┐  ┌──────────┐
    │  ERROR   │  │  FAILED  │ (temporary)
    │(disabled)│  └────┬─────┘
    └──────────┘       │ retry/next file
                       ▼
                  ┌──────────┐
                  │  READY   │
                  └──────────┘
```

### Match Status Transitions

```
   START
     │
     ▼
┌─────────┐
│ LOOKUP  │
└────┬────┘
     │
     ├── path found in cache ──────▶ MATCHED
     │
     ├── path not in cache ─────────▶ UNMATCHED
     │
     ├── multiple candidates ──────▶ UNCERTAIN
     │
     └── API error ────────────────▶ ERROR
```

## 7. Validation Rules

### Configuration Validation

| Field | Rule | Error |
|-------|------|-------|
| url | Must match `^https?://` | "URL must start with http:// or https://" |
| url | Must be valid URL | "Invalid URL format" |
| api_key | Non-empty | "API key is required" |
| api_key | No whitespace | "API key must not contain whitespace" |
| timeout_seconds | 1-300 | "Timeout must be between 1 and 300 seconds" |

### Enrichment Validation

| Field | Rule | Error |
|-------|------|-------|
| original_language | ISO 639-2/B or None | "Invalid language code" |
| external_source | "radarr" or "sonarr" | "Unknown external source" |
| external_id | Positive integer | "Invalid external ID" |
| season_number | Non-negative if present | "Invalid season number" |
| episode_number | Positive if present | "Invalid episode number" |

## 8. Indexes and Lookups

### Radarr Path Index
- **Key**: Normalized file path (string)
- **Value**: Movie ID (int)
- **Built**: On first `on_file_scanned` call in session
- **Cleared**: On session end

### Sonarr Parse Cache
- **Key**: Normalized file path (string)
- **Value**: SonarrParseResult
- **Built**: Lazily on each `on_file_scanned` call
- **Cleared**: On session end

### Path Normalization
1. Resolve symlinks
2. Convert to absolute path
3. Normalize separators to forward slash
4. Remove trailing slashes
