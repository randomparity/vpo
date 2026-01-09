"""Fixtures specific to real media policy integration tests.

This module provides:
- FFprobeIntrospector fixture for verifying output files
- Policy file fixtures
- Helper functions for file verification
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from vpo.db.types import IntrospectionResult
    from vpo.introspector.ffprobe import FFprobeIntrospector


@pytest.fixture
def introspector(
    ffprobe_available: bool,
) -> FFprobeIntrospector:
    """Provide an FFprobeIntrospector for verifying output files.

    Skips the test if ffprobe is not available.
    """
    if not ffprobe_available:
        pytest.skip("ffprobe not available")

    from vpo.introspector.ffprobe import FFprobeIntrospector

    return FFprobeIntrospector()


@pytest.fixture
def copy_video(tmp_path: Path):
    """Factory fixture to copy a video to a temporary location.

    Useful for tests that modify the file in-place.

    Usage:
        def test_something(copy_video, generated_basic_h264):
            working_copy = copy_video(generated_basic_h264, "test.mkv")
            # Modify working_copy...
    """

    def _copy(source: Path | None, filename: str) -> Path:
        if source is None:
            pytest.skip("Source video not available")
        dest = tmp_path / filename
        shutil.copy2(source, dest)
        return dest

    return _copy


def get_track_by_type_and_index(
    result: IntrospectionResult,
    track_type: str,
    type_index: int = 0,
):
    """Get a track from introspection result by type and index within type.

    Args:
        result: Introspection result
        track_type: "video", "audio", or "subtitle"
        type_index: Index within tracks of that type (0 = first, 1 = second, etc.)

    Returns:
        TrackInfo for the matched track, or None if not found.
    """
    type_tracks = [t for t in result.tracks if t.track_type == track_type]
    if type_index < len(type_tracks):
        return type_tracks[type_index]
    return None


def get_audio_tracks(result: IntrospectionResult):
    """Get all audio tracks from introspection result."""
    return [t for t in result.tracks if t.track_type == "audio"]


def get_video_tracks(result: IntrospectionResult):
    """Get all video tracks from introspection result."""
    return [t for t in result.tracks if t.track_type == "video"]


def get_subtitle_tracks(result: IntrospectionResult):
    """Get all subtitle tracks from introspection result."""
    return [t for t in result.tracks if t.track_type == "subtitle"]
