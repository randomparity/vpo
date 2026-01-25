"""Tests for CLI display formatting utilities."""

from vpo.cli.formatting import (
    DEFAULT_STATUS_COLOR,
    JOB_STATUS_COLORS,
    format_job_status,
    get_status_color,
)
from vpo.db import JobStatus


class TestJobStatusColors:
    """Tests for JOB_STATUS_COLORS mapping."""

    def test_contains_all_statuses(self):
        """All JobStatus values have a color mapping."""
        for status in JobStatus:
            assert status in JOB_STATUS_COLORS

    def test_colors_are_strings(self):
        """All colors are non-empty strings."""
        for status, color in JOB_STATUS_COLORS.items():
            assert isinstance(color, str)
            assert len(color) > 0

    def test_expected_colors(self):
        """Specific statuses have expected colors."""
        assert JOB_STATUS_COLORS[JobStatus.QUEUED] == "yellow"
        assert JOB_STATUS_COLORS[JobStatus.RUNNING] == "blue"
        assert JOB_STATUS_COLORS[JobStatus.COMPLETED] == "green"
        assert JOB_STATUS_COLORS[JobStatus.FAILED] == "red"
        assert JOB_STATUS_COLORS[JobStatus.CANCELLED] == "bright_black"


class TestGetStatusColor:
    """Tests for get_status_color function."""

    def test_returns_color_for_valid_status(self):
        """Returns correct color for valid status."""
        assert get_status_color(JobStatus.COMPLETED) == "green"
        assert get_status_color(JobStatus.FAILED) == "red"

    def test_all_statuses_have_colors(self):
        """All statuses return a color (not default)."""
        for status in JobStatus:
            color = get_status_color(status)
            assert color != DEFAULT_STATUS_COLOR


class TestFormatJobStatus:
    """Tests for format_job_status function."""

    def test_returns_tuple(self):
        """Returns a tuple of (value, color)."""
        result = format_job_status(JobStatus.RUNNING)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_value_matches_status(self):
        """First element is the status value."""
        value, _ = format_job_status(JobStatus.COMPLETED)
        assert value == "completed"

    def test_color_matches_mapping(self):
        """Second element is the color from mapping."""
        _, color = format_job_status(JobStatus.FAILED)
        assert color == "red"
