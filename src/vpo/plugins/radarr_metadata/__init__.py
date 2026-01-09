"""Radarr metadata enrichment plugin.

This plugin connects to a Radarr instance to fetch movie metadata and enrich
scanned files with original language, title, and year information.
"""

from vpo.plugins.radarr_metadata.plugin import (
    RadarrMetadataPlugin,
)

__all__ = ["RadarrMetadataPlugin"]
