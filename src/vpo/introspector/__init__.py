"""Introspector module for Video Policy Orchestrator.

This module provides media introspection capabilities:

- MediaIntrospector: Protocol defining the introspection interface
- FFprobeIntrospector: Production implementation using ffprobe
- StubIntrospector: Stub implementation for testing
- MediaIntrospectionError: Exception for introspection failures

Formatters for introspection results:
- format_human: Human-readable output
- format_json: JSON output
- format_track_line: Format a single track for display
- track_to_dict: Convert TrackInfo to dictionary
"""

from vpo.introspector.ffprobe import FFprobeIntrospector
from vpo.introspector.formatters import (
    format_human,
    format_json,
    format_track_line,
    frame_rate_to_fps,
    track_to_dict,
)
from vpo.introspector.interface import (
    MediaIntrospectionError,
    MediaIntrospector,
)
from vpo.introspector.stub import StubIntrospector

__all__ = [
    "MediaIntrospector",
    "MediaIntrospectionError",
    "FFprobeIntrospector",
    "StubIntrospector",
    # Formatters
    "format_human",
    "format_json",
    "format_track_line",
    "frame_rate_to_fps",
    "track_to_dict",
]
