"""Tests for policy run command formatting helpers."""

from pathlib import Path

from vpo.cli.policy import (
    _format_file_snapshot,
    _format_result_human,
    _format_result_json,
    _format_snapshot_json,
)
from vpo.domain.models import TrackInfo
from vpo.policy.types import (
    FileProcessingResult,
    FileSnapshot,
    PhaseOutcome,
    PhaseResult,
)


def _make_track(
    index: int,
    track_type: str = "video",
    codec: str | None = "h264",
    language: str | None = None,
    title: str | None = None,
    is_default: bool = False,
    width: int | None = None,
    height: int | None = None,
    channels: int | None = None,
    channel_layout: str | None = None,
) -> TrackInfo:
    """Create a TrackInfo for testing."""
    return TrackInfo(
        index=index,
        track_type=track_type,
        codec=codec,
        language=language,
        title=title,
        is_default=is_default,
        width=width,
        height=height,
        channels=channels,
        channel_layout=channel_layout,
    )


def _make_snapshot(
    tracks: list[TrackInfo] | None = None,
    container_format: str | None = "matroska,webm",
    size_bytes: int = 8_589_934_592,
) -> FileSnapshot:
    """Create a FileSnapshot for testing."""
    return FileSnapshot(
        container_format=container_format,
        size_bytes=size_bytes,
        tracks=tuple(tracks or []),
    )


def _make_phase_result(
    name: str = "normalize",
    success: bool = True,
    changes: int = 2,
    duration: float = 0.5,
    outcome: PhaseOutcome = PhaseOutcome.COMPLETED,
) -> PhaseResult:
    """Create a PhaseResult for testing."""
    return PhaseResult(
        phase_name=name,
        success=success,
        duration_seconds=duration,
        operations_executed=(),
        changes_made=changes,
        outcome=outcome,
    )


def _make_result(
    file_before: FileSnapshot | None = None,
    file_after: FileSnapshot | None = None,
    success: bool = True,
    phase_results: tuple[PhaseResult, ...] | None = None,
) -> FileProcessingResult:
    """Create a FileProcessingResult for testing."""
    phases = phase_results or (_make_phase_result(),)
    return FileProcessingResult(
        file_path=Path("/media/movie.mkv"),
        success=success,
        phase_results=phases,
        total_duration_seconds=1.5,
        total_changes=2,
        phases_completed=1,
        phases_failed=0,
        phases_skipped=0,
        file_before=file_before,
        file_after=file_after,
    )


# =============================================================================
# _format_file_snapshot tests
# =============================================================================


class TestFormatFileSnapshot:
    """Tests for _format_file_snapshot()."""

    def test_shows_label_and_container(self):
        snap = _make_snapshot(
            container_format="matroska,webm", size_bytes=8_589_934_592
        )
        lines = _format_file_snapshot(snap, "Before")
        assert lines[0] == "Before:"
        assert "Matroska" in lines[1]
        assert "8.0 GB" in lines[1]

    def test_groups_tracks_by_type(self):
        tracks = [
            _make_track(0, "video", "h264", width=1920, height=1080),
            _make_track(1, "audio", "aac", "eng", channel_layout="stereo"),
            _make_track(2, "subtitle", "ass", "eng"),
        ]
        snap = _make_snapshot(tracks=tracks)
        lines = _format_file_snapshot(snap, "Before")
        text = "\n".join(lines)
        assert "Video:" in text
        assert "Audio:" in text
        assert "Subtitles:" in text

    def test_empty_tracks(self):
        snap = _make_snapshot(tracks=[])
        lines = _format_file_snapshot(snap, "After")
        text = "\n".join(lines)
        assert "(no tracks)" in text

    def test_none_container_shows_unknown(self):
        snap = _make_snapshot(container_format=None)
        lines = _format_file_snapshot(snap, "Before")
        assert "Unknown" in lines[1]

    def test_other_tracks_grouped(self):
        tracks = [_make_track(0, "attachment", "ttf")]
        snap = _make_snapshot(tracks=tracks)
        lines = _format_file_snapshot(snap, "Before")
        text = "\n".join(lines)
        assert "Other:" in text


# =============================================================================
# _format_result_human tests
# =============================================================================


class TestFormatResultHumanSnapshots:
    """Tests for snapshot sections in _format_result_human()."""

    def test_verbose_shows_before_and_after(self):
        before = _make_snapshot(
            tracks=[_make_track(0, "video", "h264", width=1920, height=1080)],
            size_bytes=8_000_000_000,
        )
        after = _make_snapshot(
            tracks=[_make_track(0, "video", "hevc", width=1920, height=1080)],
            size_bytes=4_000_000_000,
        )
        result = _make_result(file_before=before, file_after=after)
        output = _format_result_human(result, Path("/media/movie.mkv"), verbose=True)

        assert "Before:" in output
        assert "After:" in output
        assert "h264" in output
        assert "hevc" in output

    def test_verbose_dry_run_shows_no_after(self):
        before = _make_snapshot(
            tracks=[_make_track(0, "video", "h264")],
        )
        result = _make_result(file_before=before, file_after=None)
        output = _format_result_human(result, Path("/media/movie.mkv"), verbose=True)

        assert "Before:" in output
        assert "(dry-run, no changes applied)" in output

    def test_verbose_no_snapshots_shows_not_scanned(self):
        result = _make_result(file_before=None, file_after=None)
        output = _format_result_human(result, Path("/media/movie.mkv"), verbose=True)

        assert "(file not scanned)" in output

    def test_non_verbose_has_no_snapshots(self):
        before = _make_snapshot()
        after = _make_snapshot()
        result = _make_result(file_before=before, file_after=after)
        output = _format_result_human(result, Path("/media/movie.mkv"), verbose=False)

        assert "Before:" not in output
        assert "After:" not in output

    def test_verbose_includes_phase_details(self):
        before = _make_snapshot()
        after = _make_snapshot()
        result = _make_result(file_before=before, file_after=after)
        output = _format_result_human(result, Path("/media/movie.mkv"), verbose=True)

        assert "Phase details:" in output
        assert "[OK]" in output


# =============================================================================
# _format_snapshot_json tests
# =============================================================================


class TestFormatSnapshotJson:
    """Tests for _format_snapshot_json()."""

    def test_includes_all_fields(self):
        tracks = [_make_track(0, "video", "h264")]
        snap = _make_snapshot(
            tracks=tracks,
            container_format="matroska,webm",
            size_bytes=1_000_000,
        )
        data = _format_snapshot_json(snap)
        assert data["container_format"] == "matroska,webm"
        assert data["size_bytes"] == 1_000_000
        assert len(data["tracks"]) == 1
        assert data["tracks"][0]["codec"] == "h264"

    def test_empty_tracks(self):
        snap = _make_snapshot(tracks=[])
        data = _format_snapshot_json(snap)
        assert data["tracks"] == []


# =============================================================================
# _format_result_json snapshot tests
# =============================================================================


class TestFormatResultJsonSnapshots:
    """Tests for before/after keys in _format_result_json()."""

    def test_includes_before_and_after(self):
        before = _make_snapshot(size_bytes=8_000_000_000)
        after = _make_snapshot(size_bytes=4_000_000_000)
        result = _make_result(file_before=before, file_after=after)
        data = _format_result_json(result, Path("/media/movie.mkv"))

        assert "before" in data
        assert data["before"]["size_bytes"] == 8_000_000_000
        assert "after" in data
        assert data["after"]["size_bytes"] == 4_000_000_000

    def test_omits_before_when_none(self):
        result = _make_result(file_before=None, file_after=None)
        data = _format_result_json(result, Path("/media/movie.mkv"))

        assert "before" not in data
        assert "after" not in data

    def test_before_only_for_dry_run(self):
        before = _make_snapshot()
        result = _make_result(file_before=before, file_after=None)
        data = _format_result_json(result, Path("/media/movie.mkv"))

        assert "before" in data
        assert "after" not in data
