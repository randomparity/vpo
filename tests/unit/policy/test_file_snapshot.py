"""Tests for FileSnapshot dataclass."""

import pytest

from vpo.domain.models import FileInfo, TrackInfo
from vpo.policy.types import FileSnapshot


def _make_track(
    index: int,
    track_type: str = "video",
    codec: str | None = "h264",
    language: str | None = None,
) -> TrackInfo:
    """Create a minimal TrackInfo for testing."""
    return TrackInfo(index=index, track_type=track_type, codec=codec, language=language)


def _make_file_info(
    tracks: list[TrackInfo] | None = None,
    container_format: str | None = "matroska,webm",
    size_bytes: int = 1_000_000,
) -> FileInfo:
    """Create a minimal FileInfo for testing."""
    from datetime import datetime, timezone
    from pathlib import Path

    return FileInfo(
        path=Path("/test/file.mkv"),
        filename="file.mkv",
        directory=Path("/test"),
        extension=".mkv",
        size_bytes=size_bytes,
        modified_at=datetime.now(timezone.utc),
        container_format=container_format,
        tracks=tracks or [],
    )


class TestFileSnapshotFromFileInfo:
    """Tests for FileSnapshot.from_file_info()."""

    def test_extracts_container_format(self):
        info = _make_file_info(container_format="matroska,webm")
        snap = FileSnapshot.from_file_info(info)
        assert snap.container_format == "matroska,webm"

    def test_extracts_size_bytes(self):
        info = _make_file_info(size_bytes=8_589_934_592)
        snap = FileSnapshot.from_file_info(info)
        assert snap.size_bytes == 8_589_934_592

    def test_extracts_tracks_as_tuple(self):
        tracks = [
            _make_track(0, "video", "h264"),
            _make_track(1, "audio", "aac", "eng"),
        ]
        info = _make_file_info(tracks=tracks)
        snap = FileSnapshot.from_file_info(info)
        assert isinstance(snap.tracks, tuple)
        assert len(snap.tracks) == 2
        assert snap.tracks[0].codec == "h264"
        assert snap.tracks[1].language == "eng"

    def test_handles_none_container_format(self):
        info = _make_file_info(container_format=None)
        snap = FileSnapshot.from_file_info(info)
        assert snap.container_format is None

    def test_handles_empty_tracks(self):
        info = _make_file_info(tracks=[])
        snap = FileSnapshot.from_file_info(info)
        assert snap.tracks == ()

    def test_extracts_container_tags_sorted(self):
        info = _make_file_info()
        # Manually set container_tags (FileInfo is not frozen)
        info.container_tags = {"title": "Movie Title", "encoder": "libebml v1.4.2"}
        snap = FileSnapshot.from_file_info(info)
        assert snap.container_tags == (
            ("encoder", "libebml v1.4.2"),
            ("title", "Movie Title"),
        )

    def test_none_container_tags(self):
        info = _make_file_info()
        info.container_tags = None
        snap = FileSnapshot.from_file_info(info)
        assert snap.container_tags is None

    def test_empty_container_tags(self):
        info = _make_file_info()
        info.container_tags = {}
        snap = FileSnapshot.from_file_info(info)
        assert snap.container_tags is None


class TestFileSnapshotFrozen:
    """Tests that FileSnapshot is immutable."""

    def test_cannot_set_container_format(self):
        snap = FileSnapshot(container_format="mkv", size_bytes=100, tracks=())
        with pytest.raises(AttributeError):
            snap.container_format = "mp4"  # type: ignore[misc]

    def test_cannot_set_size_bytes(self):
        snap = FileSnapshot(container_format="mkv", size_bytes=100, tracks=())
        with pytest.raises(AttributeError):
            snap.size_bytes = 200  # type: ignore[misc]

    def test_cannot_set_tracks(self):
        snap = FileSnapshot(container_format="mkv", size_bytes=100, tracks=())
        with pytest.raises(AttributeError):
            snap.tracks = ()  # type: ignore[misc]
