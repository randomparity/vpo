"""Hello World VPO Plugin.

A minimal example plugin demonstrating the VPO plugin architecture.
Use this as a starting point for your own plugins.

This plugin logs a greeting when files are scanned, showing how to:
- Inherit from BaseAnalyzerPlugin
- Subscribe to events
- Use the plugin logger
- Return metadata enrichments (optional)

Usage:
    1. Install: pip install -e .
    2. Verify: vpo plugins list
    3. Run: vpo scan /path/to/videos
"""

from vpo.plugin_sdk import (
    BaseAnalyzerPlugin,
    get_logger,
)

logger = get_logger(__name__)


class HelloWorldPlugin(BaseAnalyzerPlugin):
    """A simple greeting plugin that logs when files are scanned.

    Attributes:
        name: Unique plugin identifier (kebab-case)
        version: Plugin version (semver)
        description: Human-readable description
        events: List of events to subscribe to
        min_api_version: Minimum VPO plugin API version
        max_api_version: Maximum VPO plugin API version
    """

    name = "hello-world"
    version = "0.1.0"
    description = "Example plugin that greets scanned files"
    author = "VPO Examples"
    events = ["file.scanned"]

    # API version compatibility (accepts all 1.x releases)
    min_api_version = "1.0.0"
    max_api_version = "1.99.99"

    def on_file_scanned(self, event):
        """Handle file.scanned events.

        This method is called after ffprobe introspection completes.
        Use it to analyze files, log information, or enrich metadata.

        Args:
            event: FileScannedEvent containing:
                - file_info: FileInfo dataclass with file metadata
                - tracks: List of TrackInfo dataclasses

        Returns:
            Optional dict of metadata to add to the file, or None.
            Returned metadata is stored in the database.
        """
        file_path = event.file_info.path
        track_count = len(event.tracks)

        # Log a greeting
        self.logger.info(
            "Hello from %s! Found %d tracks in %s",
            self.name,
            track_count,
            file_path.name,
        )

        # Example: Return custom metadata to store with the file
        # This is optional - return None if you don't need to add metadata
        return {
            "hello_world_analyzed": True,
            "hello_world_track_count": track_count,
        }


# Create the plugin instance
# This is what the entry point references
plugin = HelloWorldPlugin()
