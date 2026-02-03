"""Radarr API client for metadata retrieval.

This module provides an HTTP client for the Radarr v3 API, supporting
connection validation and metadata fetching for movie files.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from vpo.config.models import PluginConnectionConfig
from vpo.plugin_sdk.helpers import extract_date_from_iso, normalize_path_for_matching
from vpo.plugins.radarr_metadata.models import (
    RadarrCache,
    RadarrLanguage,
    RadarrMovie,
    RadarrMovieFile,
)

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
normalize_path = normalize_path_for_matching


class RadarrConnectionError(Exception):
    """Raised when connection to Radarr fails."""


class RadarrAuthError(RadarrConnectionError):
    """Raised when Radarr API key is invalid."""


class RadarrClient:
    """HTTP client for Radarr v3 API.

    Provides methods for connection validation and metadata fetching.
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
        """Get Radarr system status.

        Returns:
            Status response from /api/v3/system/status.

        Raises:
            RadarrAuthError: If API key is invalid (401).
            RadarrConnectionError: If connection fails.
        """
        client = self._get_client()
        try:
            response = client.get("/api/v3/system/status")
            if response.status_code == 401:
                raise RadarrAuthError("Invalid API key")
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError as e:
            raise RadarrConnectionError(f"Cannot connect to Radarr: {e}") from e
        except httpx.TimeoutException as e:
            raise RadarrConnectionError(f"Connection timeout: {e}") from e
        except httpx.HTTPStatusError as e:
            raise RadarrConnectionError(f"HTTP error: {e}") from e

    def validate_connection(self) -> bool:
        """Validate connection to Radarr.

        Tests the API connection by calling the status endpoint.

        Returns:
            True if connection is valid.

        Raises:
            RadarrAuthError: If API key is invalid.
            RadarrConnectionError: If connection fails.
        """
        status = self.get_status()
        app_name = status.get("appName", "")
        if app_name != "Radarr":
            raise RadarrConnectionError(
                f"Expected Radarr, got {app_name}. Check the URL."
            )
        logger.info(
            "Connected to Radarr %s",
            status.get("version", "unknown"),
        )
        return True

    def get_movies(self, tag_map: dict[int, str] | None = None) -> list[RadarrMovie]:
        """Get all movies from Radarr.

        Args:
            tag_map: Optional tag ID to label mapping for resolving tag names.

        Returns:
            List of RadarrMovie objects.

        Raises:
            RadarrConnectionError: If request fails.
        """
        client = self._get_client()
        try:
            response = client.get("/api/v3/movie")
            response.raise_for_status()
            data = response.json()
            return [self._parse_movie_response(m, tag_map=tag_map) for m in data]
        except httpx.HTTPError as e:
            raise RadarrConnectionError(f"Failed to get movies: {e}") from e

    def get_movie_files(self) -> list[RadarrMovieFile]:
        """Get all movie files from Radarr.

        Returns:
            List of RadarrMovieFile objects.

        Raises:
            RadarrConnectionError: If request fails.
        """
        client = self._get_client()
        try:
            response = client.get("/api/v3/moviefile")
            response.raise_for_status()
            data = response.json()
            return [self._parse_movie_file_response(f) for f in data]
        except httpx.HTTPError as e:
            raise RadarrConnectionError(f"Failed to get movie files: {e}") from e

    def get_tags(self) -> dict[int, str]:
        """Get all tags from Radarr.

        Returns:
            Mapping of tag ID to tag label.

        Raises:
            RadarrConnectionError: If request fails.
        """
        client = self._get_client()
        try:
            response = client.get("/api/v3/tag")
            response.raise_for_status()
            data = response.json()
            return {t["id"]: t["label"] for t in data if "id" in t and "label" in t}
        except httpx.HTTPError as e:
            raise RadarrConnectionError(f"Failed to get tags: {e}") from e

    def _parse_movie_response(
        self, data: dict[str, Any], tag_map: dict[int, str] | None = None
    ) -> RadarrMovie:
        """Parse movie JSON response to RadarrMovie.

        Args:
            data: Movie JSON object from API.
            tag_map: Optional tag ID to label mapping for resolving tag names.

        Returns:
            RadarrMovie dataclass.
        """
        original_language = None
        if lang_data := data.get("originalLanguage"):
            original_language = RadarrLanguage(
                id=lang_data.get("id", 0),
                name=lang_data.get("name", "Unknown"),
            )

        # Parse release dates - Radarr returns ISO 8601 datetime strings
        # We extract just the date portion (YYYY-MM-DD) if present
        digital_release = extract_date_from_iso(data.get("digitalRelease"))
        physical_release = extract_date_from_iso(data.get("physicalRelease"))
        cinema_release = extract_date_from_iso(data.get("inCinemas"))

        # Flatten genres array to comma-separated string
        genres_list = data.get("genres")
        genres = ", ".join(genres_list) if genres_list else None

        # Extract collection name from nested object
        collection_name = None
        if collection := data.get("collection"):
            collection_name = collection.get("name")

        # Flatten nested ratings
        rating_tmdb = None
        rating_imdb = None
        if ratings := data.get("ratings"):
            if tmdb_rating := ratings.get("tmdb"):
                rating_tmdb = tmdb_rating.get("value")
            if imdb_rating := ratings.get("imdb"):
                rating_imdb = imdb_rating.get("value")

        # Resolve tag IDs to names
        tags = None
        if tag_map and (tag_ids := data.get("tags")):
            tag_names = [tag_map[tid] for tid in tag_ids if tid in tag_map]
            tags = ", ".join(tag_names) if tag_names else None

        # monitored field
        monitored = data.get("monitored")

        return RadarrMovie(
            id=data["id"],
            title=data.get("title", ""),
            original_title=data.get("originalTitle"),
            original_language=original_language,
            year=data.get("year", 0),
            path=data.get("path", ""),
            has_file=data.get("hasFile", False),
            imdb_id=data.get("imdbId"),
            tmdb_id=data.get("tmdbId"),
            digital_release=digital_release,
            physical_release=physical_release,
            cinema_release=cinema_release,
            certification=data.get("certification") or None,
            genres=genres,
            runtime=data.get("runtime"),
            status=data.get("status"),
            collection_name=collection_name,
            studio=data.get("studio") or None,
            rating_tmdb=rating_tmdb,
            rating_imdb=rating_imdb,
            popularity=data.get("popularity"),
            monitored=monitored,
            tags=tags,
        )

    def _parse_movie_file_response(self, data: dict[str, Any]) -> RadarrMovieFile:
        """Parse movie file JSON response to RadarrMovieFile.

        Args:
            data: MovieFile JSON object from API.

        Returns:
            RadarrMovieFile dataclass.
        """
        return RadarrMovieFile(
            id=data["id"],
            movie_id=data["movieId"],
            path=data.get("path", ""),
            relative_path=data.get("relativePath", ""),
            size=data.get("size", 0),
            edition=data.get("edition") or None,
            release_group=data.get("releaseGroup") or None,
            scene_name=data.get("sceneName") or None,
        )

    def build_cache(self) -> RadarrCache:
        """Build session cache from Radarr API.

        Fetches tags, movies, and movie files, builds path-to-movie index.

        Returns:
            RadarrCache with movies, files, tags, and path index.

        Raises:
            RadarrConnectionError: If API requests fail.
        """
        logger.debug("Building Radarr cache...")

        # Fetch tags first (graceful on failure)
        tag_map: dict[int, str] = {}
        try:
            tag_map = self.get_tags()
        except RadarrConnectionError:
            logger.warning("Radarr: failed to fetch tags, continuing without")

        movies = self.get_movies(tag_map=tag_map)
        files = self.get_movie_files()

        cache = RadarrCache.empty()
        cache.tags = tag_map

        # Index movies by ID
        for movie in movies:
            cache.movies[movie.id] = movie

        # Index files by path and map to movies
        for file in files:
            normalized_path = normalize_path(file.path)
            cache.files[normalized_path] = file
            cache.path_to_movie[normalized_path] = file.movie_id

        logger.info(
            "Radarr cache built: %d movies, %d files, %d tags",
            len(cache.movies),
            len(cache.files),
            len(cache.tags),
        )
        return cache
