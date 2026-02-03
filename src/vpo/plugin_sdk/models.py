"""Shared models for metadata enrichment plugins.

This module provides common dataclasses used by metadata plugins
(e.g., Radarr, Sonarr) for enrichment data.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class MatchStatus(Enum):
    """Status of file matching attempt."""

    MATCHED = "matched"
    UNMATCHED = "unmatched"
    UNCERTAIN = "uncertain"
    ERROR = "error"


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

    # Release date fields (ISO 8601 format, e.g., "2024-01-15")
    # Used by file_timestamp policy operation to set file mtime
    release_date: str | None = None  # Primary release date (digital/air)
    cinema_release: str | None = None  # Theatrical release (movies)
    digital_release: str | None = None  # Digital release (movies)
    physical_release: str | None = None  # Physical release (movies)
    air_date: str | None = None  # Episode air date (TV)
    premiere_date: str | None = None  # Series premiere (TV)

    # Common metadata fields (v1.1.0)
    original_title: str | None = None  # Original title (before translation)
    certification: str | None = None  # Content rating (PG-13, R, TV-MA, etc.)
    genres: str | None = None  # Comma-separated genre list
    runtime: int | None = None  # Runtime in minutes
    status: str | None = None  # Release/series status
    monitored: bool | None = None  # Monitoring status in Radarr/Sonarr
    tags: str | None = None  # Comma-separated tag names
    popularity: float | None = None  # Popularity score

    # Movie-specific fields (Radarr, v1.1.0)
    collection_name: str | None = None  # Movie collection name
    studio: str | None = None  # Studio name
    rating_tmdb: float | None = None  # TMDb rating
    rating_imdb: float | None = None  # IMDb rating
    edition: str | None = None  # Edition (Director's Cut, Extended, etc.)
    release_group: str | None = None  # Release group identifier
    scene_name: str | None = None  # Scene release name

    # TV-specific fields (Sonarr, v1.1.0)
    network: str | None = None  # TV network (HBO, Netflix, etc.)
    series_type: str | None = None  # standard/daily/anime
    tvmaze_id: int | None = None  # TVMaze identifier
    season_count: int | None = None  # Number of seasons
    total_episode_count: int | None = None  # Total episode count
    absolute_episode_number: int | None = None  # Absolute episode number (anime)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for plugin return value.

        Returns:
            Dictionary suitable for merging into FileInfo.
        """
        # Required fields always included
        result: dict[str, Any] = {
            "original_language": self.original_language,
            "external_source": self.external_source,
            "external_id": self.external_id,
            "external_title": self.external_title,
        }

        # Optional fields only included when present
        optional_fields = [
            "external_year",
            "imdb_id",
            "tmdb_id",
            "series_title",
            "season_number",
            "episode_number",
            "episode_title",
            "tvdb_id",
            "release_date",
            "cinema_release",
            "digital_release",
            "physical_release",
            "air_date",
            "premiere_date",
            # v1.1.0 common fields
            "original_title",
            "certification",
            "genres",
            "runtime",
            "status",
            "monitored",
            "tags",
            "popularity",
            # v1.1.0 movie fields
            "collection_name",
            "studio",
            "rating_tmdb",
            "rating_imdb",
            "edition",
            "release_group",
            "scene_name",
            # v1.1.0 TV fields
            "network",
            "series_type",
            "tvmaze_id",
            "season_count",
            "total_episode_count",
            "absolute_episode_number",
        ]
        for field in optional_fields:
            value = getattr(self, field)
            if value is not None:
                result[field] = value

        return result


@dataclass(frozen=True)
class MatchResult:
    """Result of attempting to match a file to external service."""

    status: MatchStatus
    enrichment: MetadataEnrichment | None = None
    error_message: str | None = None
    candidates: tuple[int, ...] = ()  # IDs of potential matches if uncertain
