"""Radarr API response models and cache structures.

This module defines dataclasses for Radarr API responses and the session cache
used for efficient path-based lookups during file scanning.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Re-export shared models for backward compatibility
from vpo.plugin_sdk.models import (
    MatchResult,
    MatchStatus,
    MetadataEnrichment,
)

__all__ = [
    "MatchResult",
    "MatchStatus",
    "MetadataEnrichment",
    "RadarrCache",
    "RadarrLanguage",
    "RadarrMovie",
    "RadarrMovieFile",
]


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
