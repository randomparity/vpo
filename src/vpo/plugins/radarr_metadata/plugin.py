"""Radarr metadata enrichment plugin.

This plugin connects to a Radarr instance to fetch movie metadata and enrich
scanned files with original language, title, and year information.
"""

from __future__ import annotations

import logging
from typing import Any

from vpo.config.models import PluginConnectionConfig
from vpo.language import normalize_language
from vpo.plugin.events import FileScannedEvent
from vpo.plugin_sdk.models import MetadataEnrichment
from vpo.plugins.radarr_metadata.client import (
    RadarrAuthError,
    RadarrClient,
    RadarrConnectionError,
    normalize_path,
)
from vpo.plugins.radarr_metadata.models import (
    RadarrCache,
    RadarrMovie,
)

logger = logging.getLogger(__name__)


class RadarrMetadataPlugin:
    """Radarr metadata enrichment plugin.

    Connects to Radarr to fetch movie metadata and enrich scanned files
    with original language, title, and year information.

    Implements the AnalyzerPlugin protocol.
    """

    name: str = "radarr-metadata"
    version: str = "1.0.0"
    events: tuple[str, ...] = ("file.scanned",)

    def __init__(self, config: PluginConnectionConfig) -> None:
        """Initialize the plugin.

        Args:
            config: Connection configuration for Radarr API.

        Raises:
            RadarrAuthError: If API key is invalid.
            RadarrConnectionError: If connection validation fails.
        """
        self._config = config
        self._client = RadarrClient(config)
        self._cache: RadarrCache | None = None
        self._disabled = False  # Set True on auth failure

        # Validate connection on startup
        try:
            self._client.validate_connection()
            logger.info(
                "Radarr plugin initialized: %s",
                config.url,
            )
        except RadarrAuthError:
            logger.error(
                "Radarr plugin disabled: invalid API key for %s",
                config.url,
            )
            self._disabled = True
            raise
        except RadarrConnectionError as e:
            logger.warning(
                "Radarr plugin: connection failed to %s: %s",
                config.url,
                e,
            )
            raise

    def on_file_scanned(self, event: FileScannedEvent) -> dict[str, Any] | None:
        """Enrich file metadata from Radarr.

        Called after a file is scanned. Looks up the file in Radarr's
        library by path and returns enrichment data if found.

        Args:
            event: FileScannedEvent with file path and info.

        Returns:
            Dict of enrichment data to merge into file_info,
            or None if file not found or error occurs.
        """
        if self._disabled:
            return None

        try:
            # Build cache on first call
            if self._cache is None:
                self._cache = self._client.build_cache()

            # Look up file by path
            file_path = normalize_path(str(event.file_path))
            movie = self._cache.lookup_by_path(file_path)

            if movie is None:
                logger.debug(
                    "Radarr: no match for %s",
                    event.file_path,
                )
                return None

            # Create enrichment
            enrichment = self._create_enrichment(movie)
            logger.debug(
                "Radarr: matched %s to '%s' (%d)",
                event.file_path,
                movie.title,
                movie.id,
            )
            return enrichment.to_dict()

        except RadarrAuthError:
            logger.error("Radarr: authentication failed, disabling plugin")
            self._disabled = True
            return None
        except RadarrConnectionError as e:
            logger.warning("Radarr: API error: %s", e)
            return None
        except Exception as e:
            logger.error("Radarr: unexpected error: %s", e)
            return None

    def _create_enrichment(self, movie: RadarrMovie) -> MetadataEnrichment:
        """Create enrichment data from Radarr movie.

        Args:
            movie: RadarrMovie object.

        Returns:
            MetadataEnrichment with normalized language code.
        """
        # Normalize language name to ISO 639-2/B
        original_language = None
        if movie.original_language:
            original_language = normalize_language(
                movie.original_language.name,
                warn_on_conversion=False,
            )

        return MetadataEnrichment(
            original_language=original_language,
            external_source="radarr",
            external_id=movie.id,
            external_title=movie.title,
            external_year=movie.year if movie.year > 0 else None,
            imdb_id=movie.imdb_id,
            tmdb_id=movie.tmdb_id,
        )

    def on_policy_evaluate(self, event: Any) -> None:
        """Not implemented - plugin only subscribes to file.scanned."""
        pass

    def on_plan_complete(self, event: Any) -> None:
        """Not implemented - plugin only subscribes to file.scanned."""
        pass

    def close(self) -> None:
        """Clean up HTTP client resources."""
        self._client.close()
