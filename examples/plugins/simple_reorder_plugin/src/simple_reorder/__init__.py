"""Simple Reorder Plugin - Example VPO Analyzer Plugin.

This module demonstrates how to create a VPO plugin using the Plugin SDK.
It analyzes scanned files and reports on subtitle track positioning.
"""

from __future__ import annotations

import logging
from typing import Any

from vpo.plugin_sdk import BaseAnalyzerPlugin

logger = logging.getLogger(__name__)


class SimpleReorderPlugin(BaseAnalyzerPlugin):
    """Example analyzer plugin that reports on subtitle track positions.

    This plugin demonstrates:
    - Using BaseAnalyzerPlugin for reduced boilerplate
    - Handling file.scanned events
    - Returning metadata enrichment
    - Proper plugin registration

    The plugin analyzes media files to check if subtitle tracks
    are positioned immediately after video tracks (the preferred
    arrangement for most media players).
    """

    # Plugin metadata (required)
    name = "simple-reorder"
    version = "1.0.0"
    description = "Reports on subtitle track positioning in media files"
    author = "VPO Team"

    # API version compatibility
    min_api_version = "1.0.0"
    max_api_version = "1.99.99"

    # Events this plugin subscribes to
    events = ["file.scanned"]

    def on_file_scanned(self, event: Any) -> dict[str, Any] | None:
        """Handle file.scanned event.

        Analyzes track positions and returns metadata about subtitle
        placement relative to video tracks.

        Args:
            event: FileScannedEvent containing file_info and tracks.

        Returns:
            Metadata dict with analysis results, or None if no analysis.
        """
        try:
            tracks = event.tracks
            file_path = event.file_info.path if event.file_info else "unknown"

            # Count tracks by type
            video_tracks = [t for t in tracks if t.track_type == "video"]
            subtitle_tracks = [t for t in tracks if t.track_type == "subtitle"]
            audio_tracks = [t for t in tracks if t.track_type == "audio"]

            if not subtitle_tracks:
                logger.debug(
                    "simple-reorder: No subtitles in %s",
                    file_path,
                )
                return None

            # Find the last video track index
            last_video_index = max((t.index for t in video_tracks), default=-1)

            # Find the first subtitle index
            first_subtitle_index = min(t.index for t in subtitle_tracks)

            # Check if subtitles are well-positioned (after video, before/with audio)
            # Ideal: video, audio, subtitle OR video, subtitle, audio
            audio_indices = [t.index for t in audio_tracks]
            has_audio_between = any(
                last_video_index < idx < first_subtitle_index for idx in audio_indices
            )

            # Report findings
            analysis = {
                "subtitle_count": len(subtitle_tracks),
                "first_subtitle_index": first_subtitle_index,
                "last_video_index": last_video_index,
                "subtitles_after_video": first_subtitle_index > last_video_index,
                "audio_between_video_and_subtitle": has_audio_between,
            }

            logger.info(
                "simple-reorder: Analyzed %s - %d subtitles, first at index %d",
                file_path,
                len(subtitle_tracks),
                first_subtitle_index,
            )

            return analysis

        except Exception as e:
            logger.warning(
                "simple-reorder: Error analyzing file: %s",
                e,
            )
            return None


# Plugin instance for entry point discovery
# This is what gets loaded when VPO discovers the plugin
plugin = SimpleReorderPlugin()


# Alternative: Allow direct class import for testing
__all__ = ["SimpleReorderPlugin", "plugin"]
