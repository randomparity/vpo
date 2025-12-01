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
