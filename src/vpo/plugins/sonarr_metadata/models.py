"""Sonarr API response models and cache structures.

This module defines dataclasses for Sonarr API responses and the session cache
used for efficient path-based lookups during file scanning.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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
    path: str  # Series folder path
    original_language: SonarrLanguage | None = None
    imdb_id: str | None = None
    tvdb_id: int | None = None
    # Release date (ISO 8601 format from Sonarr API)
    first_aired: str | None = None  # firstAired from API (series premiere)


@dataclass(frozen=True)
class SonarrEpisode:
    """Episode object from Sonarr API."""

    id: int
    series_id: int
    season_number: int
    episode_number: int
    title: str
    has_file: bool = False
    # Air date (ISO 8601 format from Sonarr API)
    air_date: str | None = None  # airDate from API (episode air date)


@dataclass(frozen=True)
class SonarrParseResult:
    """Result from Sonarr parse endpoint.

    The parse endpoint identifies series and episodes from a file path.
    May return None for series if the file cannot be identified.
    """

    series: SonarrSeries | None
    episodes: tuple[SonarrEpisode, ...]


@dataclass
class SonarrCache:
    """Session cache for Sonarr API data.

    Populated lazily using the parse endpoint as files are scanned.
    """

    series: dict[int, SonarrSeries] = field(default_factory=dict)
    parse_results: dict[str, SonarrParseResult] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> SonarrCache:
        """Create an empty cache."""
        return cls(series={}, parse_results={})

    def lookup_by_path(self, path: str) -> SonarrParseResult | None:
        """Look up cached parse result by file path.

        Args:
            path: Normalized file path to look up.

        Returns:
            SonarrParseResult if cached, None otherwise.
        """
        return self.parse_results.get(path)
