"""Tests for vpo.db.json_schemas module."""

import pytest
from pydantic import ValidationError

from vpo.db.json_schemas import (
    ApplyJobSummary,
    JobProgressSchema,
    MoveJobSummary,
    PluginMetadataSchema,
    ScanJobSummary,
    TranscodeJobSummary,
    get_summary_schema,
)


class TestPluginMetadataSchema:
    """Tests for PluginMetadataSchema."""

    def test_valid_structure(self):
        """Valid nested plugin metadata validates."""
        data = {
            "radarr": {"movie_id": 123, "title": "Movie Name"},
            "sonarr": {"series_id": 456, "active": True},
        }
        schema = PluginMetadataSchema.model_validate(data)
        assert schema is not None

    def test_empty_dict(self):
        """Empty dict is valid."""
        schema = PluginMetadataSchema.model_validate({})
        assert schema is not None

    def test_mixed_value_types(self):
        """Scalar types (str, int, float, bool, None) are valid."""
        data = {
            "plugin": {
                "string_val": "text",
                "int_val": 42,
                "float_val": 3.14,
                "bool_val": True,
                "null_val": None,
            }
        }
        schema = PluginMetadataSchema.model_validate(data)
        assert schema is not None


class TestScanJobSummary:
    """Tests for ScanJobSummary."""

    def test_valid_summary(self):
        """Valid scan summary validates."""
        data = {
            "total_discovered": 100,
            "scanned": 95,
            "skipped": 5,
            "added": 10,
            "removed": 2,
            "errors": 0,
        }
        summary = ScanJobSummary.model_validate(data)
        assert summary.scanned == 95
        assert summary.added == 10
        assert summary.errors == 0

    def test_defaults(self):
        """Missing fields use defaults."""
        summary = ScanJobSummary.model_validate({})
        assert summary.total_discovered == 0
        assert summary.scanned == 0
        assert summary.skipped == 0
        assert summary.added == 0
        assert summary.removed == 0
        assert summary.errors == 0

    def test_negative_count_rejected(self):
        """Negative counts are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ScanJobSummary.model_validate({"scanned": -1})
        assert "scanned" in str(exc_info.value)

    def test_extra_field_rejected(self):
        """Extra fields are rejected (extra='forbid')."""
        with pytest.raises(ValidationError) as exc_info:
            ScanJobSummary.model_validate({"scanned": 10, "unknown_field": "value"})
        assert "unknown_field" in str(exc_info.value)


class TestApplyJobSummary:
    """Tests for ApplyJobSummary."""

    def test_valid_summary(self):
        """Valid apply summary validates."""
        data = {
            "policy_name": "cleanup.yaml",
            "files_affected": 5,
            "actions_applied": ["remove_track", "set_default"],
        }
        summary = ApplyJobSummary.model_validate(data)
        assert summary.policy_name == "cleanup.yaml"
        assert summary.files_affected == 5
        assert len(summary.actions_applied) == 2

    def test_missing_policy_name(self):
        """Missing required policy_name fails."""
        with pytest.raises(ValidationError) as exc_info:
            ApplyJobSummary.model_validate({"files_affected": 5})
        assert "policy_name" in str(exc_info.value)

    def test_defaults(self):
        """Optional fields use defaults."""
        summary = ApplyJobSummary.model_validate({"policy_name": "test.yaml"})
        assert summary.files_affected == 0
        assert summary.actions_applied == []


class TestTranscodeJobSummary:
    """Tests for TranscodeJobSummary."""

    def test_valid_summary(self):
        """Valid transcode summary validates."""
        data = {
            "input_file": "/path/to/input.mkv",
            "output_file": "/path/to/output.mkv",
            "input_size_bytes": 1000000000,
            "output_size_bytes": 500000000,
            "duration_seconds": 3600.5,
            "video_codec": "hevc",
            "audio_tracks_processed": 2,
        }
        summary = TranscodeJobSummary.model_validate(data)
        assert summary.input_size_bytes == 1000000000
        assert summary.output_size_bytes == 500000000
        assert summary.video_codec == "hevc"

    def test_defaults(self):
        """Missing fields use defaults."""
        summary = TranscodeJobSummary.model_validate({})
        assert summary.input_file == ""
        assert summary.output_file == ""
        assert summary.input_size_bytes == 0
        assert summary.output_size_bytes == 0
        assert summary.duration_seconds == 0.0
        assert summary.video_codec is None
        assert summary.audio_tracks_processed == 0

    def test_negative_size_rejected(self):
        """Negative sizes are rejected."""
        with pytest.raises(ValidationError):
            TranscodeJobSummary.model_validate({"input_size_bytes": -1})


class TestMoveJobSummary:
    """Tests for MoveJobSummary."""

    def test_valid_summary(self):
        """Valid move summary validates."""
        data = {
            "source_path": "/path/to/source.mkv",
            "destination_path": "/path/to/dest.mkv",
            "size_bytes": 500000000,
        }
        summary = MoveJobSummary.model_validate(data)
        assert summary.source_path == "/path/to/source.mkv"
        assert summary.destination_path == "/path/to/dest.mkv"
        assert summary.size_bytes == 500000000

    def test_defaults(self):
        """Missing fields use defaults."""
        summary = MoveJobSummary.model_validate({})
        assert summary.source_path == ""
        assert summary.destination_path == ""
        assert summary.size_bytes == 0


class TestJobProgressSchema:
    """Tests for JobProgressSchema."""

    def test_valid_progress(self):
        """Valid progress validates."""
        data = {
            "percent": 75.5,
            "frame_current": 1500,
            "frame_total": 2000,
            "fps": 45.2,
            "eta_seconds": 120,
        }
        progress = JobProgressSchema.model_validate(data)
        assert progress.percent == 75.5
        assert progress.frame_current == 1500
        assert progress.frame_total == 2000
        assert progress.fps == 45.2
        assert progress.eta_seconds == 120

    def test_percent_required(self):
        """Percent field is required."""
        with pytest.raises(ValidationError) as exc_info:
            JobProgressSchema.model_validate({})
        assert "percent" in str(exc_info.value)

    def test_percent_range_low(self):
        """Percent below 0 is rejected."""
        with pytest.raises(ValidationError):
            JobProgressSchema.model_validate({"percent": -1.0})

    def test_percent_range_high(self):
        """Percent above 100 is rejected."""
        with pytest.raises(ValidationError):
            JobProgressSchema.model_validate({"percent": 100.1})

    def test_percent_boundary_values(self):
        """Percent boundary values (0 and 100) are accepted."""
        progress_0 = JobProgressSchema.model_validate({"percent": 0.0})
        assert progress_0.percent == 0.0

        progress_100 = JobProgressSchema.model_validate({"percent": 100.0})
        assert progress_100.percent == 100.0

    def test_optional_fields_none(self):
        """Optional fields default to None."""
        progress = JobProgressSchema.model_validate({"percent": 50.0})
        assert progress.frame_current is None
        assert progress.frame_total is None
        assert progress.time_current is None
        assert progress.time_total is None
        assert progress.fps is None
        assert progress.bitrate is None
        assert progress.size_current is None
        assert progress.eta_seconds is None

    def test_negative_frames_rejected(self):
        """Negative frame counts are rejected."""
        with pytest.raises(ValidationError):
            JobProgressSchema.model_validate({"percent": 50.0, "frame_current": -1})

    def test_negative_fps_rejected(self):
        """Negative fps is rejected."""
        with pytest.raises(ValidationError):
            JobProgressSchema.model_validate({"percent": 50.0, "fps": -1.0})

    def test_extra_field_rejected(self):
        """Extra fields are rejected (extra='forbid')."""
        with pytest.raises(ValidationError):
            JobProgressSchema.model_validate(
                {"percent": 50.0, "unknown_field": "value"}
            )


class TestGetSummarySchema:
    """Tests for get_summary_schema function."""

    def test_scan_type(self):
        """Scan type returns ScanJobSummary."""
        assert get_summary_schema("scan") is ScanJobSummary

    def test_apply_type(self):
        """Apply type returns ApplyJobSummary."""
        assert get_summary_schema("apply") is ApplyJobSummary

    def test_transcode_type(self):
        """Transcode type returns TranscodeJobSummary."""
        assert get_summary_schema("transcode") is TranscodeJobSummary

    def test_move_type(self):
        """Move type returns MoveJobSummary."""
        assert get_summary_schema("move") is MoveJobSummary

    def test_unknown_type(self):
        """Unknown type returns None."""
        assert get_summary_schema("unknown") is None
        assert get_summary_schema("") is None
