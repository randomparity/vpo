"""Unit tests for apply command formatting functions.

Tests for dry-run output formatting with track dispositions.
"""

import json
from pathlib import Path

from video_policy_orchestrator.policy.models import (
    ContainerChange,
    Plan,
    TrackDisposition,
)

# =============================================================================
# Helper functions for creating test data
# =============================================================================


def make_track_disposition(
    track_index: int,
    track_type: str,
    action: str,
    reason: str,
    **kwargs,
) -> TrackDisposition:
    """Create a test TrackDisposition."""
    return TrackDisposition(
        track_index=track_index,
        track_type=track_type,
        codec=kwargs.get("codec"),
        language=kwargs.get("language"),
        title=kwargs.get("title"),
        channels=kwargs.get("channels"),
        resolution=kwargs.get("resolution"),
        action=action,
        reason=reason,
    )


def make_plan_with_dispositions(
    track_dispositions: tuple[TrackDisposition, ...],
    tracks_kept: int,
    tracks_removed: int,
    container_change: ContainerChange | None = None,
) -> Plan:
    """Create a test Plan with track dispositions."""
    return Plan(
        file_id="test-file-id",
        file_path=Path("/test/movie.mkv"),
        policy_version=3,
        actions=(),
        requires_remux=tracks_removed > 0 or container_change is not None,
        track_dispositions=track_dispositions,
        tracks_kept=tracks_kept,
        tracks_removed=tracks_removed,
        container_change=container_change,
    )


# =============================================================================
# Tests for _format_track_dispositions (T026)
# =============================================================================


class TestFormatTrackDispositions:
    """Tests for _format_track_dispositions helper function."""

    def test_formats_single_kept_track(self) -> None:
        """Should format a single kept track correctly."""
        from video_policy_orchestrator.cli.apply import _format_track_dispositions

        dispositions = (
            make_track_disposition(
                track_index=0,
                track_type="video",
                action="KEEP",
                reason="video track",
                codec="hevc",
                resolution="1920x1080",
            ),
        )

        result = _format_track_dispositions(dispositions)

        assert "KEEP" in result
        assert "video" in result.lower()
        assert "0" in result  # track index

    def test_formats_removed_track_with_reason(self) -> None:
        """Should format removed tracks with reason."""
        from video_policy_orchestrator.cli.apply import _format_track_dispositions

        dispositions = (
            make_track_disposition(
                track_index=0,
                track_type="video",
                action="KEEP",
                reason="video track",
            ),
            make_track_disposition(
                track_index=1,
                track_type="audio",
                action="REMOVE",
                reason="language not in keep list",
                codec="ac3",
                language="fra",
            ),
        )

        result = _format_track_dispositions(dispositions)

        assert "REMOVE" in result
        assert "fra" in result.lower()
        assert "language not in keep list" in result

    def test_formats_track_metadata(self) -> None:
        """Should include track metadata in output."""
        from video_policy_orchestrator.cli.apply import _format_track_dispositions

        dispositions = (
            make_track_disposition(
                track_index=1,
                track_type="audio",
                action="KEEP",
                reason="language in keep list",
                codec="truehd",
                language="eng",
                title="TrueHD 7.1",
                channels=8,
            ),
        )

        result = _format_track_dispositions(dispositions)

        assert "truehd" in result.lower()
        assert "eng" in result
        assert "7.1" in result or "8" in result or "TrueHD" in result

    def test_formats_mixed_dispositions(self) -> None:
        """Should format mixed KEEP/REMOVE dispositions."""
        from video_policy_orchestrator.cli.apply import _format_track_dispositions

        dispositions = (
            make_track_disposition(
                track_index=0,
                track_type="video",
                action="KEEP",
                reason="video track",
                codec="hevc",
            ),
            make_track_disposition(
                track_index=1,
                track_type="audio",
                action="KEEP",
                reason="language in keep list",
                codec="aac",
                language="eng",
            ),
            make_track_disposition(
                track_index=2,
                track_type="audio",
                action="REMOVE",
                reason="language not in keep list",
                codec="ac3",
                language="fra",
            ),
            make_track_disposition(
                track_index=3,
                track_type="subtitle",
                action="KEEP",
                reason="no filter applied",
                codec="subrip",
                language="eng",
            ),
        )

        result = _format_track_dispositions(dispositions)

        # Should have entries for all tracks
        assert result.count("KEEP") == 3
        assert result.count("REMOVE") == 1

    def test_empty_dispositions(self) -> None:
        """Should handle empty dispositions gracefully."""
        from video_policy_orchestrator.cli.apply import _format_track_dispositions

        result = _format_track_dispositions(())

        # Should return empty or minimal output
        assert result == "" or "track" not in result.lower()


# =============================================================================
# Tests for _format_container_change (T026)
# =============================================================================


class TestFormatContainerChange:
    """Tests for _format_container_change helper function."""

    def test_formats_mkv_to_mp4_conversion(self) -> None:
        """Should format MKV to MP4 conversion."""
        from video_policy_orchestrator.cli.apply import _format_container_change

        change = ContainerChange(
            source_format="mkv",
            target_format="mp4",
            warnings=(),
            incompatible_tracks=(),
        )

        result = _format_container_change(change)

        assert "mkv" in result.lower()
        assert "mp4" in result.lower()

    def test_formats_avi_to_mkv_conversion(self) -> None:
        """Should format AVI to MKV conversion."""
        from video_policy_orchestrator.cli.apply import _format_container_change

        change = ContainerChange(
            source_format="avi",
            target_format="mkv",
            warnings=(),
            incompatible_tracks=(),
        )

        result = _format_container_change(change)

        assert "avi" in result.lower()
        assert "mkv" in result.lower()

    def test_formats_conversion_with_warnings(self) -> None:
        """Should include warnings in output."""
        from video_policy_orchestrator.cli.apply import _format_container_change

        change = ContainerChange(
            source_format="mkv",
            target_format="mp4",
            warnings=("PGS subtitles not supported in MP4",),
            incompatible_tracks=(3,),
        )

        result = _format_container_change(change)

        assert "warning" in result.lower() or "subtitle" in result.lower()

    def test_none_container_change(self) -> None:
        """Should handle None container change."""
        from video_policy_orchestrator.cli.apply import _format_container_change

        result = _format_container_change(None)

        assert result == ""


# =============================================================================
# Tests for JSON dry-run output format (T027)
# =============================================================================


class TestDryRunJsonOutput:
    """Tests for JSON dry-run output format."""

    def test_json_includes_track_dispositions(self) -> None:
        """JSON output should include track dispositions."""
        from video_policy_orchestrator.cli.apply import _format_dry_run_json

        dispositions = (
            make_track_disposition(
                track_index=0,
                track_type="video",
                action="KEEP",
                reason="video track",
                codec="hevc",
            ),
            make_track_disposition(
                track_index=1,
                track_type="audio",
                action="KEEP",
                reason="language in keep list",
                codec="aac",
                language="eng",
            ),
            make_track_disposition(
                track_index=2,
                track_type="audio",
                action="REMOVE",
                reason="language not in keep list",
                codec="ac3",
                language="fra",
            ),
        )

        plan = make_plan_with_dispositions(
            track_dispositions=dispositions,
            tracks_kept=2,
            tracks_removed=1,
        )

        result = _format_dry_run_json(
            policy_path=Path("/test/policy.yaml"),
            policy_version=3,
            target_path=Path("/test/movie.mkv"),
            container="mkv",
            plan=plan,
        )

        data = json.loads(result)

        # Check plan section has track_dispositions
        assert "track_dispositions" in data["plan"]
        assert len(data["plan"]["track_dispositions"]) == 3

        # Check disposition structure
        disp = data["plan"]["track_dispositions"][2]
        assert disp["track_index"] == 2
        assert disp["track_type"] == "audio"
        assert disp["action"] == "REMOVE"
        assert "reason" in disp

    def test_json_includes_track_counts(self) -> None:
        """JSON output should include tracks_kept and tracks_removed counts."""
        from video_policy_orchestrator.cli.apply import _format_dry_run_json

        dispositions = (
            make_track_disposition(
                track_index=0,
                track_type="video",
                action="KEEP",
                reason="video track",
            ),
            make_track_disposition(
                track_index=1,
                track_type="audio",
                action="KEEP",
                reason="language in keep list",
            ),
            make_track_disposition(
                track_index=2,
                track_type="audio",
                action="REMOVE",
                reason="language not in keep list",
            ),
        )

        plan = make_plan_with_dispositions(
            track_dispositions=dispositions,
            tracks_kept=2,
            tracks_removed=1,
        )

        result = _format_dry_run_json(
            policy_path=Path("/test/policy.yaml"),
            policy_version=3,
            target_path=Path("/test/movie.mkv"),
            container="mkv",
            plan=plan,
        )

        data = json.loads(result)

        assert data["plan"]["tracks_kept"] == 2
        assert data["plan"]["tracks_removed"] == 1

    def test_json_includes_container_change(self) -> None:
        """JSON output should include container_change when present."""
        from video_policy_orchestrator.cli.apply import _format_dry_run_json

        container_change = ContainerChange(
            source_format="avi",
            target_format="mkv",
            warnings=(),
            incompatible_tracks=(),
        )

        plan = make_plan_with_dispositions(
            track_dispositions=(),
            tracks_kept=3,
            tracks_removed=0,
            container_change=container_change,
        )

        result = _format_dry_run_json(
            policy_path=Path("/test/policy.yaml"),
            policy_version=3,
            target_path=Path("/test/movie.avi"),
            container="avi",
            plan=plan,
        )

        data = json.loads(result)

        assert "container_change" in data["plan"]
        cc = data["plan"]["container_change"]
        assert cc["source_format"] == "avi"
        assert cc["target_format"] == "mkv"


# =============================================================================
# Tests for dry-run output summary line (T031)
# =============================================================================


class TestDryRunSummaryLine:
    """Tests for summary line with track counts."""

    def test_summary_includes_track_removal_count(self) -> None:
        """Summary should include track removal count when > 0."""
        from video_policy_orchestrator.cli.apply import _format_dry_run_output

        dispositions = (
            make_track_disposition(
                track_index=0,
                track_type="video",
                action="KEEP",
                reason="video track",
            ),
            make_track_disposition(
                track_index=1,
                track_type="audio",
                action="KEEP",
                reason="language in keep list",
            ),
            make_track_disposition(
                track_index=2,
                track_type="audio",
                action="REMOVE",
                reason="language not in keep list",
            ),
        )

        plan = make_plan_with_dispositions(
            track_dispositions=dispositions,
            tracks_kept=2,
            tracks_removed=1,
        )

        result = _format_dry_run_output(
            policy_path=Path("/test/policy.yaml"),
            policy_version=3,
            target_path=Path("/test/movie.mkv"),
            plan=plan,
        )

        # Summary should mention track removal
        assert "1" in result
        assert "track" in result.lower()
        assert "removed" in result.lower() or "remove" in result.lower()

    def test_summary_shows_no_changes_when_empty(self) -> None:
        """Summary should indicate no changes when plan is empty."""
        plan = Plan(
            file_id="test-file-id",
            file_path=Path("/test/movie.mkv"),
            policy_version=3,
            actions=(),
            requires_remux=False,
        )

        from video_policy_orchestrator.cli.apply import _format_dry_run_output

        result = _format_dry_run_output(
            policy_path=Path("/test/policy.yaml"),
            policy_version=3,
            target_path=Path("/test/movie.mkv"),
            plan=plan,
        )

        assert "no changes" in result.lower()
