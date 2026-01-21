"""Tests for scanner data models."""

import json
from datetime import datetime, timezone
from pathlib import Path

from vpo.scanner.models import ScanResult


class TestScanResult:
    """Tests for ScanResult dataclass."""

    def test_default_values(self):
        """ScanResult has correct default values."""
        job_id = "test-job-id"
        directory = Path("/videos")
        started_at = datetime.now(timezone.utc)

        result = ScanResult(
            job_id=job_id,
            directory=directory,
            started_at=started_at,
        )

        assert result.job_id == job_id
        assert result.directory == directory
        assert result.started_at == started_at
        assert result.completed_at is None
        assert result.total_discovered == 0
        assert result.scanned == 0
        assert result.skipped == 0
        assert result.added == 0
        assert result.removed == 0
        assert result.errors == 0
        assert result.incremental is True

    def test_with_all_values(self):
        """ScanResult stores all provided values."""
        started_at = datetime.now(timezone.utc)
        completed_at = datetime.now(timezone.utc)

        result = ScanResult(
            job_id="test-123",
            directory=Path("/videos/movies"),
            started_at=started_at,
            completed_at=completed_at,
            total_discovered=100,
            scanned=80,
            skipped=15,
            added=50,
            removed=5,
            errors=5,
            incremental=False,
        )

        assert result.total_discovered == 100
        assert result.scanned == 80
        assert result.skipped == 15
        assert result.added == 50
        assert result.removed == 5
        assert result.errors == 5
        assert result.incremental is False
        assert result.completed_at == completed_at

    def test_to_summary_dict(self):
        """to_summary_dict returns dict with all counts."""
        result = ScanResult(
            job_id="test-123",
            directory=Path("/videos"),
            started_at=datetime.now(timezone.utc),
            total_discovered=100,
            scanned=80,
            skipped=15,
            added=50,
            removed=5,
            errors=5,
        )

        summary = result.to_summary_dict()

        assert isinstance(summary, dict)
        assert summary["total_discovered"] == 100
        assert summary["scanned"] == 80
        assert summary["skipped"] == 15
        assert summary["added"] == 50
        assert summary["removed"] == 5
        assert summary["errors"] == 5

    def test_to_summary_dict_default_values(self):
        """to_summary_dict returns zeros for default values."""
        result = ScanResult(
            job_id="test-123",
            directory=Path("/videos"),
            started_at=datetime.now(timezone.utc),
        )

        summary = result.to_summary_dict()

        assert summary["total_discovered"] == 0
        assert summary["scanned"] == 0
        assert summary["skipped"] == 0
        assert summary["added"] == 0
        assert summary["removed"] == 0
        assert summary["errors"] == 0

    def test_to_summary_dict_excludes_other_fields(self):
        """to_summary_dict only includes count fields."""
        result = ScanResult(
            job_id="test-123",
            directory=Path("/videos"),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            incremental=False,
            scanned=10,
        )

        summary = result.to_summary_dict()

        # Should only have count fields
        expected_keys = {
            "total_discovered",
            "scanned",
            "skipped",
            "added",
            "removed",
            "errors",
        }
        assert set(summary.keys()) == expected_keys
        # Should not include job_id, directory, timestamps, or incremental
        assert "job_id" not in summary
        assert "directory" not in summary
        assert "started_at" not in summary
        assert "completed_at" not in summary
        assert "incremental" not in summary

    def test_to_summary_json(self):
        """to_summary_json returns valid JSON string."""
        result = ScanResult(
            job_id="test-123",
            directory=Path("/videos"),
            started_at=datetime.now(timezone.utc),
            total_discovered=100,
            scanned=80,
            skipped=15,
            added=50,
            removed=5,
            errors=5,
        )

        json_str = result.to_summary_json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    def test_to_summary_json_matches_dict(self):
        """to_summary_json produces JSON matching to_summary_dict."""
        result = ScanResult(
            job_id="test-123",
            directory=Path("/videos"),
            started_at=datetime.now(timezone.utc),
            total_discovered=100,
            scanned=80,
            skipped=15,
            added=50,
            removed=5,
            errors=5,
        )

        json_str = result.to_summary_json()
        parsed = json.loads(json_str)
        dict_result = result.to_summary_dict()

        assert parsed == dict_result
