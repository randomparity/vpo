"""Tests for job summary text generation."""

from video_policy_orchestrator.jobs.summary import generate_summary_text


class TestGenerateSummaryText:
    """Tests for generate_summary_text function."""

    def test_returns_none_for_none_summary(self):
        """Returns None when summary_raw is None."""
        result = generate_summary_text("scan", None)
        assert result is None

    def test_returns_none_for_unknown_job_type(self):
        """Returns None for unknown job type."""
        result = generate_summary_text("unknown_type", {"data": "value"})
        assert result is None

    def test_returns_none_for_malformed_summary(self):
        """Returns None when summary data is malformed."""
        # Wrong type - should not raise, just return None
        result = generate_summary_text("scan", "not a dict")  # type: ignore
        assert result is None


class TestScanJobSummary:
    """Tests for scan job summary generation."""

    def test_basic_scan_summary(self):
        """Generates basic scan summary."""
        summary = {"scanned": 10}
        result = generate_summary_text("scan", summary)
        assert result == "Scanned 10 files"

    def test_scan_with_new_files(self):
        """Includes added count in scan summary."""
        summary = {"scanned": 10, "added": 3}
        result = generate_summary_text("scan", summary)
        assert result == "Scanned 10 files, 3 new"

    def test_scan_with_removed_files(self):
        """Includes removed count in scan summary."""
        summary = {"scanned": 10, "removed": 2}
        result = generate_summary_text("scan", summary)
        assert result == "Scanned 10 files, 2 removed"

    def test_scan_with_unchanged_files(self):
        """Includes skipped count in scan summary."""
        summary = {"scanned": 10, "skipped": 5}
        result = generate_summary_text("scan", summary)
        assert result == "Scanned 10 files, 5 unchanged"

    def test_scan_with_errors(self):
        """Includes error count in scan summary."""
        summary = {"scanned": 10, "errors": 1}
        result = generate_summary_text("scan", summary)
        assert result == "Scanned 10 files, 1 error"

    def test_scan_with_all_fields(self):
        """Includes all fields in scan summary."""
        summary = {
            "scanned": 100,
            "added": 10,
            "removed": 5,
            "skipped": 82,
            "errors": 3,
        }
        result = generate_summary_text("scan", summary)
        assert result == "Scanned 100 files, 10 new, 5 removed, 82 unchanged, 3 errors"

    def test_scan_with_zero_values_excluded(self):
        """Zero values are excluded from scan summary."""
        summary = {"scanned": 10, "added": 0, "errors": 0}
        result = generate_summary_text("scan", summary)
        assert result == "Scanned 10 files"


class TestApplyJobSummary:
    """Tests for apply job summary generation."""

    def test_basic_apply_summary(self):
        """Generates basic apply summary."""
        summary = {"policy_name": "default", "files_affected": 5}
        result = generate_summary_text("apply", summary)
        assert result == "Applied policy 'default' to 5 files"

    def test_apply_with_actions(self):
        """Includes actions in apply summary."""
        summary = {
            "policy_name": "normalize",
            "files_affected": 3,
            "actions_applied": ["reorder_tracks", "set_language"],
        }
        result = generate_summary_text("apply", summary)
        assert (
            result
            == "Applied policy 'normalize' to 3 files (reorder_tracks, set_language)"
        )

    def test_apply_with_missing_policy_name(self):
        """Uses 'unknown' for missing policy name."""
        summary = {"files_affected": 2}
        result = generate_summary_text("apply", summary)
        assert result == "Applied policy 'unknown' to 2 files"


class TestTranscodeJobSummary:
    """Tests for transcode job summary generation."""

    def test_basic_transcode_summary(self):
        """Generates basic transcode summary."""
        summary = {
            "input_file": "/path/to/input.mkv",
            "output_file": "/path/to/output.mkv",
        }
        result = generate_summary_text("transcode", summary)
        assert "\u2192" in result  # Arrow character
        assert "input.mkv" in result
        assert "output.mkv" in result

    def test_transcode_with_compression_ratio(self):
        """Includes compression ratio in transcode summary."""
        summary = {
            "input_file": "/path/to/input.mkv",
            "output_file": "/path/to/output.mkv",
            "input_size_bytes": 1000000,
            "output_size_bytes": 500000,
        }
        result = generate_summary_text("transcode", summary)
        assert "50% of original size" in result

    def test_transcode_without_size_info(self):
        """Handles missing size info in transcode summary."""
        summary = {
            "input_file": "/path/to/input.mkv",
            "output_file": "/path/to/output.mkv",
        }
        result = generate_summary_text("transcode", summary)
        assert "%" not in result  # No compression ratio

    def test_transcode_extracts_filename_only(self):
        """Extracts only filename from full path."""
        summary = {
            "input_file": "/very/long/path/to/source.mkv",
            "output_file": "/another/path/to/dest.mkv",
        }
        result = generate_summary_text("transcode", summary)
        assert "source.mkv" in result
        assert "dest.mkv" in result
        assert "/very/long" not in result


class TestMoveJobSummary:
    """Tests for move job summary generation."""

    def test_basic_move_summary(self):
        """Generates basic move summary."""
        summary = {
            "source_path": "/old/path/movie.mkv",
            "destination_path": "/new/path/",
        }
        result = generate_summary_text("move", summary)
        assert "\u2192" in result  # Arrow character
        assert "movie.mkv" in result

    def test_move_with_size_gb(self):
        """Includes size in GB for large files."""
        summary = {
            "source_path": "/path/movie.mkv",
            "destination_path": "/new/path/",
            "size_bytes": 5 * 1024 * 1024 * 1024,  # 5 GB
        }
        result = generate_summary_text("move", summary)
        assert "5.0 GB" in result

    def test_move_with_size_mb(self):
        """Includes size in MB for medium files."""
        summary = {
            "source_path": "/path/movie.mkv",
            "destination_path": "/new/path/",
            "size_bytes": 500 * 1024 * 1024,  # 500 MB
        }
        result = generate_summary_text("move", summary)
        assert "500.0 MB" in result

    def test_move_with_size_kb(self):
        """Includes size in KB for small files."""
        summary = {
            "source_path": "/path/movie.mkv",
            "destination_path": "/new/path/",
            "size_bytes": 100 * 1024,  # 100 KB
        }
        result = generate_summary_text("move", summary)
        assert "100.0 KB" in result


class TestBackwardCompatibility:
    """Test backward compatibility with imports from server.ui.models."""

    def test_import_from_jobs_module(self):
        """Can import from video_policy_orchestrator.jobs."""
        from video_policy_orchestrator.jobs import generate_summary_text as func

        assert func is generate_summary_text

    def test_import_from_models_module(self):
        """Can import from server.ui.models for backward compatibility."""
        from video_policy_orchestrator.server.ui.models import (
            generate_summary_text as func,
        )

        assert callable(func)
        # Should work the same way
        result = func("scan", {"scanned": 5})
        assert result == "Scanned 5 files"
