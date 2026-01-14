"""Sonarr metadata enrichment plugin.

This plugin connects to a Sonarr instance to fetch TV series metadata and enrich
scanned files with original language, series title, and episode information.
"""

from vpo.plugins.sonarr_metadata.plugin import (
    SonarrMetadataPlugin,
)

__all__ = ["SonarrMetadataPlugin"]
