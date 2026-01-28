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
