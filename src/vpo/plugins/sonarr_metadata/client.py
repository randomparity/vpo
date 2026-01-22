"""Sonarr API client for metadata retrieval.

This module provides an HTTP client for the Sonarr v3 API, supporting
connection validation and metadata fetching for TV episode files.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx

from vpo.config.models import PluginConnectionConfig
from vpo.plugin_sdk.helpers import extract_date_from_iso, normalize_path_for_matching
from vpo.plugins.sonarr_metadata.models import (
    SonarrEpisode,
    SonarrLanguage,
    SonarrParseResult,
    SonarrSeries,
)

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
normalize_path = normalize_path_for_matching


class SonarrConnectionError(Exception):
    """Raised when connection to Sonarr fails."""

    pass


class SonarrAuthError(SonarrConnectionError):
    """Raised when Sonarr API key is invalid."""

    pass


class SonarrClient:
    """HTTP client for Sonarr v3 API.

    Provides methods for connection validation and metadata fetching.
    Uses the parse endpoint for efficient per-file lookups.
    """

    def __init__(self, config: PluginConnectionConfig) -> None:
        """Initialize the client.

        Args:
            config: Connection configuration with URL and API key.
        """
        self._base_url = config.url.rstrip("/")
        self._api_key = config.api_key
        self._timeout = config.timeout_seconds
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self._base_url,
                timeout=self._timeout,
                headers=self._headers(),
            )
        return self._client

    def _headers(self) -> dict[str, str]:
        """Get request headers with API key.

        Returns:
            Headers dictionary with X-Api-Key.
        """
        return {"X-Api-Key": self._api_key}

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def get_status(self) -> dict[str, Any]:
        """Get Sonarr system status.

        Returns:
            Status response from /api/v3/system/status.

        Raises:
            SonarrAuthError: If API key is invalid (401).
            SonarrConnectionError: If connection fails.
        """
        client = self._get_client()
        try:
            response = client.get("/api/v3/system/status")
            if response.status_code == 401:
                raise SonarrAuthError("Invalid API key")
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError as e:
            raise SonarrConnectionError(f"Cannot connect to Sonarr: {e}") from e
        except httpx.TimeoutException as e:
            raise SonarrConnectionError(f"Connection timeout: {e}") from e
        except httpx.HTTPStatusError as e:
            raise SonarrConnectionError(f"HTTP error: {e}") from e

    def validate_connection(self) -> bool:
        """Validate connection to Sonarr.

        Tests the API connection by calling the status endpoint.

        Returns:
            True if connection is valid.

        Raises:
            SonarrAuthError: If API key is invalid.
            SonarrConnectionError: If connection fails.
        """
        status = self.get_status()
        app_name = status.get("appName", "")
        if app_name != "Sonarr":
            raise SonarrConnectionError(
                f"Expected Sonarr, got {app_name}. Check the URL."
            )
        logger.info(
            "Connected to Sonarr %s",
            status.get("version", "unknown"),
        )
        return True

    def parse(self, file_path: str) -> SonarrParseResult:
        """Parse a file path to identify series and episodes.

        Uses the Sonarr parse endpoint for efficient per-file lookups.

        Args:
            file_path: Absolute file path to parse.

        Returns:
            SonarrParseResult with series and episodes (may be None/empty).

        Raises:
            SonarrConnectionError: If request fails.
        """
        client = self._get_client()
        try:
            # URL-encode the path for query parameter
            encoded_path = quote(file_path, safe="")
            response = client.get(f"/api/v3/parse?path={encoded_path}")
            response.raise_for_status()
            data = response.json()
            return self._parse_parse_result(data)
        except httpx.HTTPError as e:
            raise SonarrConnectionError(f"Failed to parse path: {e}") from e

    def _parse_series_response(self, data: dict[str, Any]) -> SonarrSeries:
        """Parse series JSON response to SonarrSeries.

        Args:
            data: Series JSON object from API.

        Returns:
            SonarrSeries dataclass.

        Raises:
            SonarrConnectionError: If response is missing required 'id' field.
        """
        series_id = data.get("id")
        if series_id is None:
            raise SonarrConnectionError("Series response missing required 'id' field")

        original_language = None
        if lang_data := data.get("originalLanguage"):
            original_language = SonarrLanguage(
                id=lang_data.get("id", 0),
                name=lang_data.get("name", "Unknown"),
            )

        # Parse first aired date
        first_aired = extract_date_from_iso(data.get("firstAired"))

        return SonarrSeries(
            id=series_id,
            title=data.get("title", ""),
            year=data.get("year", 0),
            path=data.get("path", ""),
            original_language=original_language,
            imdb_id=data.get("imdbId"),
            tvdb_id=data.get("tvdbId"),
            first_aired=first_aired,
        )

    def _parse_episode_response(self, data: dict[str, Any]) -> SonarrEpisode:
        """Parse episode JSON response to SonarrEpisode.

        Args:
            data: Episode JSON object from API.

        Returns:
            SonarrEpisode dataclass.
        """
        # Parse air date
        air_date = extract_date_from_iso(data.get("airDate"))

        return SonarrEpisode(
            id=data.get("id", 0),
            series_id=data.get("seriesId", 0),
            season_number=data.get("seasonNumber", 0),
            episode_number=data.get("episodeNumber", 0),
            title=data.get("title", ""),
            has_file=data.get("hasFile", False),
            air_date=air_date,
        )

    def _parse_parse_result(self, data: dict[str, Any]) -> SonarrParseResult:
        """Parse full parse response to SonarrParseResult.

        Args:
            data: Parse response JSON from API.

        Returns:
            SonarrParseResult with series and episodes.
        """
        series = None
        if series_data := data.get("series"):
            series = self._parse_series_response(series_data)

        episodes: list[SonarrEpisode] = []
        if episodes_data := data.get("episodes"):
            episodes = [self._parse_episode_response(e) for e in episodes_data]

        return SonarrParseResult(
            series=series,
            episodes=tuple(episodes),
        )
