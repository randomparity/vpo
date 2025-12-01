"""Sonarr metadata enrichment plugin.

This plugin connects to a Sonarr instance to fetch TV series metadata and enrich
scanned files with original language, series title, and episode information.
"""

from __future__ import annotations

import logging
from typing import Any

from video_policy_orchestrator.config.models import PluginConnectionConfig
from video_policy_orchestrator.language import normalize_language
from video_policy_orchestrator.plugin.events import FileScannedEvent
from video_policy_orchestrator.plugin_sdk.models import MetadataEnrichment
from video_policy_orchestrator.plugins.sonarr_metadata.client import (
    SonarrAuthError,
    SonarrClient,
    SonarrConnectionError,
    normalize_path,
)
from video_policy_orchestrator.plugins.sonarr_metadata.models import (
    SonarrCache,
    SonarrParseResult,
)

logger = logging.getLogger(__name__)


class SonarrMetadataPlugin:
    """Sonarr metadata enrichment plugin.

    Connects to Sonarr to fetch TV series metadata and enrich scanned files
    with original language, series title, and episode information.

    Implements the AnalyzerPlugin protocol.
    """

    name: str = "sonarr-metadata"
    version: str = "1.0.0"
    events: tuple[str, ...] = ("file.scanned",)

    def __init__(self, config: PluginConnectionConfig) -> None:
        """Initialize the plugin.

        Args:
            config: Connection configuration for Sonarr API.

        Raises:
            SonarrAuthError: If API key is invalid.
            SonarrConnectionError: If connection validation fails.
        """
        self._config = config
        self._client = SonarrClient(config)
        self._cache = SonarrCache.empty()
        self._disabled = False  # Set True on auth failure

        # Validate connection on startup
        try:
            self._client.validate_connection()
            logger.info(
                "Sonarr plugin initialized: %s",
                config.url,
            )
        except SonarrAuthError:
            logger.error(
                "Sonarr plugin disabled: invalid API key for %s",
                config.url,
            )
            self._disabled = True
            raise
        except SonarrConnectionError as e:
            logger.warning(
                "Sonarr plugin: connection failed to %s: %s",
                config.url,
                e,
            )
            raise

    def on_file_scanned(self, event: FileScannedEvent) -> dict[str, Any] | None:
        """Enrich file metadata from Sonarr.

        Called after a file is scanned. Uses the parse endpoint to identify
        the series and episode, then returns enrichment data if found.

        Args:
            event: FileScannedEvent with file path and info.

        Returns:
            Dict of enrichment data to merge into file_info,
            or None if file not found or error occurs.
        """
        if self._disabled:
            return None

        try:
            file_path = normalize_path(str(event.file_path))

            # Check cache first
            result = self._cache.lookup_by_path(file_path)

            if result is None:
                # Call parse endpoint
                result = self._client.parse(file_path)
                # Cache the result
                self._cache.parse_results[file_path] = result
                if result.series:
                    self._cache.series[result.series.id] = result.series

            if result.series is None:
                logger.debug(
                    "Sonarr: no match for %s",
                    event.file_path,
                )
                return None

            # Create enrichment
            enrichment = self._create_enrichment(result)
            logger.debug(
                "Sonarr: matched %s to '%s' (%d)",
                event.file_path,
                result.series.title,
                result.series.id,
            )
            return enrichment.to_dict()

        except SonarrAuthError:
            logger.error("Sonarr: authentication failed, disabling plugin")
            self._disabled = True
            return None
        except SonarrConnectionError as e:
            logger.warning("Sonarr: API error: %s", e)
            return None
        except Exception as e:
            logger.error("Sonarr: unexpected error: %s", e)
            return None

    def _create_enrichment(self, result: SonarrParseResult) -> MetadataEnrichment:
        """Create enrichment data from Sonarr parse result.

        Args:
            result: SonarrParseResult with series and episodes.

        Returns:
            MetadataEnrichment with normalized language code and TV fields.
        """
        series = result.series
        episode = result.episodes[0] if result.episodes else None

        # Normalize language name to ISO 639-2/B
        original_language = None
        if series and series.original_language:
            original_language = normalize_language(
                series.original_language.name,
                warn_on_conversion=False,
            )

        return MetadataEnrichment(
            original_language=original_language,
            external_source="sonarr",
            external_id=series.id if series else 0,
            external_title=series.title if series else "",
            external_year=series.year if series and series.year > 0 else None,
            imdb_id=series.imdb_id if series else None,
            tvdb_id=series.tvdb_id if series else None,
            # TV-specific fields
            series_title=series.title if series else None,
            season_number=episode.season_number if episode else None,
            episode_number=episode.episode_number if episode else None,
            episode_title=episode.title if episode else None,
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
