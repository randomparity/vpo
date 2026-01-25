"""Tests for CLIJobLifecycle."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vpo.jobs.cli_lifecycle import CLIJobLifecycle


class TestCLIJobLifecycle:
    """Tests for CLIJobLifecycle."""

    def test_on_job_start_creates_job(self):
        """on_job_start creates a process job record."""
        conn = MagicMock()
        lifecycle = CLIJobLifecycle(conn, batch_id="batch-1", policy_name="test.yaml")

        with patch("vpo.jobs.cli_lifecycle.create_process_job") as mock_create:
            mock_job = MagicMock()
            mock_job.id = "job-123"
            mock_create.return_value = mock_job

            job_id = lifecycle.on_job_start(Path("/test.mkv"), "test.yaml", file_id=1)

        assert job_id == "job-123"
        mock_create.assert_called_once_with(
            conn,
            1,
            "/test.mkv",
            "test.yaml",
            origin="cli",
            batch_id="batch-1",
        )
        conn.commit.assert_called_once()

    def test_on_job_start_uses_instance_policy_name(self):
        """on_job_start uses instance policy_name when empty string passed."""
        conn = MagicMock()
        lifecycle = CLIJobLifecycle(conn, policy_name="default.yaml")

        with patch("vpo.jobs.cli_lifecycle.create_process_job") as mock_create:
            mock_job = MagicMock()
            mock_job.id = "job-123"
            mock_create.return_value = mock_job

            # Pass empty string for policy_name
            lifecycle.on_job_start(Path("/test.mkv"), "", file_id=None)

        # Should use the instance's policy_name
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[0][2] == "/test.mkv"
        assert call_args[0][3] == "default.yaml"

    def test_on_job_complete_updates_job(self):
        """on_job_complete updates job with completion status."""
        conn = MagicMock()
        lifecycle = CLIJobLifecycle(conn, policy_name="test.yaml")

        result = MagicMock()
        result.success = True
        result.phases_completed = 2
        result.total_changes = 5
        result.error_message = None
        result.stats_id = "stats-1"

        with patch("vpo.jobs.cli_lifecycle.complete_process_job") as mock_complete:
            lifecycle.on_job_complete("job-123", result)

        mock_complete.assert_called_once_with(
            conn,
            "job-123",
            success=True,
            phases_completed=2,
            total_changes=5,
            error_message=None,
            stats_id="stats-1",
        )
        conn.commit.assert_called_once()

    def test_on_job_complete_skips_when_no_job_id(self):
        """on_job_complete does nothing when job_id is None."""
        conn = MagicMock()
        lifecycle = CLIJobLifecycle(conn, policy_name="test.yaml")
        result = MagicMock()

        with patch("vpo.jobs.cli_lifecycle.complete_process_job") as mock_complete:
            lifecycle.on_job_complete(None, result)

        mock_complete.assert_not_called()
        conn.commit.assert_not_called()

    def test_on_job_fail_uses_retry(self):
        """on_job_fail uses fail_job_with_retry."""
        conn = MagicMock()
        lifecycle = CLIJobLifecycle(conn, policy_name="test.yaml")

        with patch("vpo.jobs.cli_lifecycle.fail_job_with_retry") as mock_fail:
            mock_fail.return_value = True
            lifecycle.on_job_fail("job-123", "Something went wrong")

        mock_fail.assert_called_once_with(conn, "job-123", "Something went wrong")

    def test_on_job_fail_skips_when_no_job_id(self):
        """on_job_fail does nothing when job_id is None."""
        conn = MagicMock()
        lifecycle = CLIJobLifecycle(conn, policy_name="test.yaml")

        with patch("vpo.jobs.cli_lifecycle.fail_job_with_retry") as mock_fail:
            lifecycle.on_job_fail(None, "error")

        mock_fail.assert_not_called()

    def test_on_job_fail_logs_on_retry_failure(self, caplog):
        """on_job_fail logs critical error when retry fails."""
        import logging

        conn = MagicMock()
        lifecycle = CLIJobLifecycle(conn, policy_name="test.yaml")

        with patch("vpo.jobs.cli_lifecycle.fail_job_with_retry") as mock_fail:
            mock_fail.return_value = False

            with caplog.at_level(logging.ERROR):
                lifecycle.on_job_fail("job-123", "error")

        assert "CRITICAL" in caplog.text
        assert "job-123" in caplog.text
        assert "orphaned" in caplog.text


class TestCLIJobLifecycleProtocol:
    """Tests that CLIJobLifecycle conforms to JobLifecycle protocol."""

    def test_has_required_methods(self):
        """CLIJobLifecycle has all required protocol methods."""
        conn = MagicMock()
        lifecycle = CLIJobLifecycle(conn, policy_name="test")

        # Check methods exist and are callable
        assert callable(lifecycle.on_job_start)
        assert callable(lifecycle.on_job_complete)
        assert callable(lifecycle.on_job_fail)
