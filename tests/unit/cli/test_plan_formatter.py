"""Unit tests for plan_formatter module."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from vpo.cli.plan_formatter import (
    _build_after_rows,
    _build_before_rows,
    _truncate,
    format_plan_json,
)
from vpo.policy.types import Plan, TrackDisposition

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_dispositions():
    """Create sample track dispositions for testing."""
    return (
        TrackDisposition(
            track_index=0,
            track_type="video",
            codec="hevc",
            language=None,
            title=None,
            channels=None,
            resolution="1920x1080",
            action="KEEP",
            reason="no filter",
            transcription_status=None,
        ),
        TrackDisposition(
            track_index=1,
            track_type="audio",
            codec="aac",
            language="eng",
            title="English",
            channels=2,
            resolution=None,
            action="KEEP",
            reason="language in keep list",
            transcription_status="main 95%",
        ),
        TrackDisposition(
            track_index=2,
            track_type="audio",
            codec="aac",
            language="eng",
            title="Commentary",
            channels=2,
            resolution=None,
            action="KEEP",
            reason="language in keep list",
            transcription_status="commentary 88%",
        ),
        TrackDisposition(
            track_index=3,
            track_type="audio",
            codec="aac",
            language="eng",
            title="Audio",
            channels=2,
            resolution=None,
            action="KEEP",
            reason="language in keep list",
            transcription_status="TBD",
        ),
    )


@pytest.fixture
def sample_plan(sample_dispositions):
    """Create a sample plan for testing."""
    return Plan(
        file_id="test-id",
        file_path=Path("/test/file.mkv"),
        policy_version=3,
        actions=(),
        requires_remux=False,
        created_at=datetime.now(timezone.utc),
        track_dispositions=sample_dispositions,
        tracks_removed=0,
        tracks_kept=4,
    )


# =============================================================================
# Transcription Status Display Tests
# =============================================================================


class TestPlanFormatterTranscriptionStatus:
    """Tests for transcription status display in plan formatter."""

    def test_analysis_column_shows_transcription_status(self, sample_dispositions):
        """ANALYSIS column (index 6) shows transcription status for audio tracks."""
        new_index_map = {0: 0, 1: 1, 2: 2, 3: 3}
        rows = _build_before_rows(sample_dispositions, new_index_map)

        # Check audio tracks have transcription status in ANALYSIS column (index 6)
        # Row 1 (audio track 1): status="main 95%"
        assert rows[1][6] == "main 95%"
        # Row 2 (audio track 2): status="commentary 88%"
        assert rows[2][6] == "commentary 88%"
        # Row 3 (audio track 3): status="TBD"
        assert rows[3][6] == "TBD"

    def test_analysis_column_shows_dash_for_non_audio(self, sample_dispositions):
        """Non-audio tracks show '-' in ANALYSIS column."""
        new_index_map = {0: 0, 1: 1, 2: 2, 3: 3}
        rows = _build_before_rows(sample_dispositions, new_index_map)

        # First row is video track - should show "-" in ANALYSIS column
        assert rows[0][6] == "-"

    def test_title_column_no_longer_includes_status(self, sample_dispositions):
        """Title column (index 5) no longer includes transcription status."""
        new_index_map = {0: 0, 1: 1, 2: 2, 3: 3}
        rows = _build_before_rows(sample_dispositions, new_index_map)

        # Title column should just be the title, not the status
        assert rows[1][5] == "English"
        assert rows[2][5] == "Commentary"
        assert rows[3][5] == "Audio"

    def test_title_truncation_without_status(self):
        """Title column is truncated to 17 chars (without status appended)."""
        dispositions = (
            TrackDisposition(
                track_index=0,
                track_type="audio",
                codec="aac",
                language="eng",
                title="Very Long Title That Should Be Truncated",
                channels=2,
                resolution=None,
                action="KEEP",
                reason="test",
                transcription_status="main 95%",
            ),
        )
        new_index_map = {0: 0}
        rows = _build_before_rows(dispositions, new_index_map)

        # Title should be truncated to 17 chars max
        title = rows[0][5]
        from vpo.cli.plan_formatter import _display_width

        assert _display_width(title) <= 17
        # Status should be in ANALYSIS column, not title
        assert rows[0][6] == "main 95%"

    def test_tbd_displayed_in_analysis_column(self):
        """'TBD' shown in ANALYSIS column for audio tracks with TBD status."""
        dispositions = (
            TrackDisposition(
                track_index=0,
                track_type="audio",
                codec="aac",
                language="eng",
                title=None,
                channels=2,
                resolution=None,
                action="KEEP",
                reason="test",
                transcription_status="TBD",
            ),
        )
        new_index_map = {0: 0}
        rows = _build_before_rows(dispositions, new_index_map)

        assert rows[0][6] == "TBD"

    def test_after_rows_include_analysis_column(self, sample_dispositions):
        """AFTER table rows also include ANALYSIS column."""
        final_order = list(sample_dispositions)
        rows = _build_after_rows(final_order)

        # ANALYSIS column (index 6) should have transcription status for audio
        assert rows[0][6] == "-"  # video track
        assert rows[1][6] == "main 95%"
        assert rows[2][6] == "commentary 88%"
        assert rows[3][6] == "TBD"

    def test_json_output_includes_transcription_status(self, sample_plan):
        """JSON output includes transcription_status field."""
        result = format_plan_json(sample_plan)

        assert "track_dispositions" in result
        dispositions = result["track_dispositions"]

        # Check that transcription_status is included
        video_disp = next(d for d in dispositions if d["track_type"] == "video")
        assert video_disp["transcription_status"] is None

        audio_disps = [d for d in dispositions if d["track_type"] == "audio"]
        assert audio_disps[0]["transcription_status"] == "main 95%"
        assert audio_disps[1]["transcription_status"] == "commentary 88%"
        assert audio_disps[2]["transcription_status"] == "TBD"


# =============================================================================
# Truncation Tests
# =============================================================================


class TestTruncation:
    """Tests for string truncation."""

    def test_truncate_short_string(self):
        """Short strings are not truncated."""
        assert _truncate("Hello", 20) == "Hello"

    def test_truncate_long_string(self):
        """Long strings are truncated with ellipsis."""
        result = _truncate("This is a very long title", 15)
        assert result.endswith("...")
        from vpo.cli.plan_formatter import _display_width

        assert _display_width(result) <= 15

    def test_truncate_exact_length(self):
        """String exactly at max length is not truncated."""
        assert _truncate("12345678901234567890", 20) == "12345678901234567890"
