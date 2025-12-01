"""Radarr API response models and cache structures.

This module defines dataclasses for Radarr API responses and the session cache
used for efficient path-based lookups during file scanning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MatchStatus(Enum):
    """Status of file matching attempt."""

    MATCHED = "matched"
    UNMATCHED = "unmatched"
    UNCERTAIN = "uncertain"
    ERROR = "error"


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
    path: str  # Movie folder path
    has_file: bool
    imdb_id: str | None = None
    tmdb_id: int | None = None


@dataclass(frozen=True)
class RadarrMovieFile:
    """Movie file object from Radarr API."""

    id: int
    movie_id: int
    path: str  # Full file path
    relative_path: str
    size: int  # Size in bytes


@dataclass
class RadarrCache:
    """Session cache for Radarr API data.

    Built from /api/v3/movie and /api/v3/moviefile endpoints.
    Provides efficient path-based lookups for file matching.
    """

    movies: dict[int, RadarrMovie] = field(default_factory=dict)
    files: dict[str, RadarrMovieFile] = field(default_factory=dict)
    path_to_movie: dict[str, int] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> RadarrCache:
        """Create an empty cache."""
        return cls(movies={}, files={}, path_to_movie={})

    def lookup_by_path(self, path: str) -> RadarrMovie | None:
        """Look up movie by file path.

        Args:
            path: Normalized file path to look up.

        Returns:
            RadarrMovie if found, None otherwise.
        """
        movie_id = self.path_to_movie.get(path)
        if movie_id is None:
            return None
        return self.movies.get(movie_id)


@dataclass(frozen=True)
class MetadataEnrichment:
    """Enrichment data from external metadata service.

    Returned by plugins to be merged into FileInfo.
    """

    original_language: str | None  # ISO 639-2/B code (e.g., "eng")
    external_source: str  # "radarr" or "sonarr"
    external_id: int  # Movie ID or Series ID
    external_title: str  # Title from external service
    external_year: int | None = None  # Year from external service

    # External identifiers
    imdb_id: str | None = None
    tmdb_id: int | None = None

    # TV-specific fields (Sonarr only)
    series_title: str | None = None
    season_number: int | None = None
    episode_number: int | None = None
    episode_title: str | None = None
    tvdb_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for plugin return value.

        Returns:
            Dictionary suitable for merging into FileInfo.
        """
        result: dict[str, Any] = {
            "original_language": self.original_language,
            "external_source": self.external_source,
            "external_id": self.external_id,
            "external_title": self.external_title,
        }
        # Add optional fields only if present
        if self.external_year is not None:
            result["external_year"] = self.external_year
        if self.imdb_id is not None:
            result["imdb_id"] = self.imdb_id
        if self.tmdb_id is not None:
            result["tmdb_id"] = self.tmdb_id
        # TV-specific fields
        if self.series_title is not None:
            result["series_title"] = self.series_title
        if self.season_number is not None:
            result["season_number"] = self.season_number
        if self.episode_number is not None:
            result["episode_number"] = self.episode_number
        if self.episode_title is not None:
            result["episode_title"] = self.episode_title
        if self.tvdb_id is not None:
            result["tvdb_id"] = self.tvdb_id
        return result


@dataclass(frozen=True)
class MatchResult:
    """Result of attempting to match a file to external service."""

    status: MatchStatus
    enrichment: MetadataEnrichment | None = None
    error_message: str | None = None
    candidates: tuple[int, ...] = ()  # IDs of potential matches if uncertain
