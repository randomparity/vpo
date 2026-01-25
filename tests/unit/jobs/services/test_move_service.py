"""Tests for MoveJobService."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.db.types import (
    Job,
    JobStatus,
    JobType,
)
from vpo.jobs.services.move import (
    MoveConfig,
    MoveJobResult,
    MoveJobService,
)


@pytest.fixture
def mock_conn():
    """Create a mock database connection."""
    conn = MagicMock(spec=sqlite3.Connection)
    return conn


@pytest.fixture
def sample_move_job():
    """Create a sample move job."""
    return Job(
        id="test-job-123",
        file_id=42,
        file_path="/source/video.mkv",
        job_type=JobType.MOVE,
        status=JobStatus.RUNNING,
        priority=100,
        policy_name=None,
        policy_json=json.dumps(
            {
                "destination_path": "/destination/video.mkv",
                "create_directories": True,
                "overwrite": False,
            }
        ),
        progress_percent=0.0,
        progress_json=None,
        created_at="2024-01-01T00:00:00+00:00",
        started_at="2024-01-01T00:00:00+00:00",
    )


class TestMoveConfig:
    """Tests for MoveConfig dataclass."""

    def test_default_values(self):
        """Default values for optional fields."""
        config = MoveConfig(destination_path=Path("/dest/file.mkv"))
        assert config.destination_path == Path("/dest/file.mkv")
        assert config.create_directories is True
        assert config.overwrite is False

    def test_custom_values(self):
        """Custom values override defaults."""
        config = MoveConfig(
            destination_path=Path("/dest/file.mkv"),
            create_directories=False,
            overwrite=True,
        )
        assert config.create_directories is False
        assert config.overwrite is True


class TestMoveJobResult:
    """Tests for MoveJobResult dataclass."""

    def test_success_result(self):
        """Success result has source and destination paths."""
        result = MoveJobResult(
            success=True,
            source_path="/source/file.mkv",
            destination_path="/dest/file.mkv",
        )
        assert result.success is True
        assert result.source_path == "/source/file.mkv"
        assert result.destination_path == "/dest/file.mkv"
        assert result.error_message is None

    def test_failure_result(self):
        """Failure result has error message."""
        result = MoveJobResult(
            success=False,
            source_path="/source/file.mkv",
            error_message="Something failed",
        )
        assert result.success is False
        assert result.source_path == "/source/file.mkv"
        assert result.destination_path is None
        assert result.error_message == "Something failed"


class TestMoveJobServiceParseConfig:
    """Tests for config parsing."""

    def test_parse_valid_config(self, mock_conn):
        """Valid JSON parses to MoveConfig."""
        service = MoveJobService(mock_conn)
        job = Job(
            id="test",
            file_id=1,
            file_path="/source/test.mkv",
            job_type=JobType.MOVE,
            status=JobStatus.RUNNING,
            priority=100,
            policy_name=None,
            policy_json=json.dumps(
                {
                    "destination_path": "/dest/test.mkv",
                    "create_directories": False,
                    "overwrite": True,
                }
            ),
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00+00:00",
            started_at="2024-01-01T00:00:00+00:00",
        )

        config, error = service._parse_config(job, None)

        assert error is None
        assert config is not None
        assert config.destination_path == Path("/dest/test.mkv")
        assert config.create_directories is False
        assert config.overwrite is True

    def test_parse_missing_policy_json(self, mock_conn):
        """Missing policy_json returns error."""
        service = MoveJobService(mock_conn)
        job = Job(
            id="test",
            file_id=1,
            file_path="/source/test.mkv",
            job_type=JobType.MOVE,
            status=JobStatus.RUNNING,
            priority=100,
            policy_name=None,
            policy_json=None,
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00+00:00",
            started_at="2024-01-01T00:00:00+00:00",
        )

        config, error = service._parse_config(job, None)

        assert config is None
        assert error is not None
        assert "Missing policy_json" in error

    def test_parse_invalid_json(self, mock_conn):
        """Invalid JSON returns error."""
        service = MoveJobService(mock_conn)
        job = Job(
            id="test",
            file_id=1,
            file_path="/source/test.mkv",
            job_type=JobType.MOVE,
            status=JobStatus.RUNNING,
            priority=100,
            policy_name=None,
            policy_json="not valid json",
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00+00:00",
            started_at="2024-01-01T00:00:00+00:00",
        )

        config, error = service._parse_config(job, None)

        assert config is None
        assert error is not None
        assert "Invalid policy JSON" in error

    def test_parse_missing_destination_path(self, mock_conn):
        """Missing destination_path returns error."""
        service = MoveJobService(mock_conn)
        job = Job(
            id="test",
            file_id=1,
            file_path="/source/test.mkv",
            job_type=JobType.MOVE,
            status=JobStatus.RUNNING,
            priority=100,
            policy_name=None,
            policy_json=json.dumps({"create_directories": True}),
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00+00:00",
            started_at="2024-01-01T00:00:00+00:00",
        )

        config, error = service._parse_config(job, None)

        assert config is None
        assert error is not None
        assert "destination_path" in error

    def test_parse_defaults_for_optional_fields(self, mock_conn):
        """Optional fields use defaults when not provided."""
        service = MoveJobService(mock_conn)
        job = Job(
            id="test",
            file_id=1,
            file_path="/source/test.mkv",
            job_type=JobType.MOVE,
            status=JobStatus.RUNNING,
            priority=100,
            policy_name=None,
            policy_json=json.dumps({"destination_path": "/dest/test.mkv"}),
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00+00:00",
            started_at="2024-01-01T00:00:00+00:00",
        )

        config, error = service._parse_config(job, None)

        assert error is None
        assert config is not None
        assert config.create_directories is True
        assert config.overwrite is False


class TestMoveJobServiceProcess:
    """Tests for the main process method."""

    def test_process_missing_file_returns_error(self, mock_conn, sample_move_job):
        """Returns error when source file doesn't exist."""
        service = MoveJobService(mock_conn)

        result = service.process(sample_move_job)

        assert result.success is False
        assert "not found" in result.error_message

    def test_process_no_policy_json_returns_error(self, mock_conn):
        """Returns error when policy_json is missing."""
        service = MoveJobService(mock_conn)
        job = Job(
            id="test",
            file_id=1,
            file_path="/source/test.mkv",
            job_type=JobType.MOVE,
            status=JobStatus.RUNNING,
            priority=100,
            policy_name=None,
            policy_json=None,
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00+00:00",
            started_at="2024-01-01T00:00:00+00:00",
        )

        result = service.process(job)

        assert result.success is False
        assert "Missing policy_json" in result.error_message

    def test_process_invalid_policy_json_returns_error(self, mock_conn):
        """Returns error when policy_json is invalid."""
        service = MoveJobService(mock_conn)
        job = Job(
            id="test",
            file_id=1,
            file_path="/source/test.mkv",
            job_type=JobType.MOVE,
            status=JobStatus.RUNNING,
            priority=100,
            policy_name=None,
            policy_json="not valid json",
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00+00:00",
            started_at="2024-01-01T00:00:00+00:00",
        )

        result = service.process(job)

        assert result.success is False
        assert "Invalid policy JSON" in result.error_message

    def test_process_successful_move(self, mock_conn, sample_move_job):
        """Successful move returns destination path."""
        service = MoveJobService(mock_conn)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("vpo.jobs.services.move.MoveExecutor") as mock_executor_cls,
            patch("vpo.jobs.services.move.update_file_path") as mock_update,
        ):
            mock_executor = MagicMock()
            mock_executor_cls.return_value = mock_executor
            mock_executor.create_plan.return_value = MagicMock()
            mock_executor.execute.return_value = MagicMock(
                success=True,
                source_path=Path("/source/video.mkv"),
                destination_path=Path("/destination/video.mkv"),
                error_message=None,
            )
            mock_update.return_value = True

            result = service.process(sample_move_job)

        assert result.success is True
        assert result.source_path == "/source/video.mkv"
        assert result.destination_path == "/destination/video.mkv"
        assert result.error_message is None

    def test_process_updates_database_on_success(self, mock_conn, sample_move_job):
        """Successful move updates file path in database."""
        service = MoveJobService(mock_conn)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("vpo.jobs.services.move.MoveExecutor") as mock_executor_cls,
            patch("vpo.jobs.services.move.update_file_path") as mock_update,
        ):
            mock_executor = MagicMock()
            mock_executor_cls.return_value = mock_executor
            mock_executor.create_plan.return_value = MagicMock()
            mock_executor.execute.return_value = MagicMock(
                success=True,
                source_path=Path("/source/video.mkv"),
                destination_path=Path("/destination/video.mkv"),
                error_message=None,
            )
            mock_update.return_value = True

            result = service.process(sample_move_job)

        assert result.success is True
        mock_update.assert_called_once_with(mock_conn, 42, "/destination/video.mkv")
        # Note: service does NOT commit - caller manages transactions

    def test_process_skips_db_update_when_no_file_id(self, mock_conn):
        """Skips database update when job has no file_id."""
        service = MoveJobService(mock_conn)
        job = Job(
            id="test-job",
            file_id=None,  # No file_id
            file_path="/source/video.mkv",
            job_type=JobType.MOVE,
            status=JobStatus.RUNNING,
            priority=100,
            policy_name=None,
            policy_json=json.dumps(
                {
                    "destination_path": "/destination/video.mkv",
                }
            ),
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00+00:00",
            started_at="2024-01-01T00:00:00+00:00",
        )

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("vpo.jobs.services.move.MoveExecutor") as mock_executor_cls,
            patch("vpo.jobs.services.move.update_file_path") as mock_update,
        ):
            mock_executor = MagicMock()
            mock_executor_cls.return_value = mock_executor
            mock_executor.create_plan.return_value = MagicMock()
            mock_executor.execute.return_value = MagicMock(
                success=True,
                source_path=Path("/source/video.mkv"),
                destination_path=Path("/destination/video.mkv"),
                error_message=None,
            )

            result = service.process(job)

        assert result.success is True
        mock_update.assert_not_called()

    def test_process_handles_move_executor_failure(self, mock_conn, sample_move_job):
        """Returns error when MoveExecutor fails."""
        service = MoveJobService(mock_conn)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("vpo.jobs.services.move.MoveExecutor") as mock_executor_cls,
        ):
            mock_executor = MagicMock()
            mock_executor_cls.return_value = mock_executor
            mock_executor.create_plan.return_value = MagicMock()
            mock_executor.execute.return_value = MagicMock(
                success=False,
                source_path=Path("/source/video.mkv"),
                destination_path=None,
                error_message="Permission denied",
            )

            result = service.process(sample_move_job)

        assert result.success is False
        assert result.source_path == "/source/video.mkv"
        assert result.destination_path is None
        assert "Permission denied" in result.error_message

    def test_parse_empty_destination_path(self, mock_conn):
        """Empty destination_path string treated as missing."""
        service = MoveJobService(mock_conn)
        job = Job(
            id="test",
            file_id=1,
            file_path="/source/test.mkv",
            job_type=JobType.MOVE,
            status=JobStatus.RUNNING,
            priority=100,
            policy_name=None,
            policy_json=json.dumps({"destination_path": ""}),
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00+00:00",
            started_at="2024-01-01T00:00:00+00:00",
        )

        config, error = service._parse_config(job, None)

        assert config is None
        assert error is not None
        assert "destination_path" in error

    def test_process_passes_correct_config_to_executor(
        self, mock_conn, sample_move_job
    ):
        """Verify config values are passed to executor correctly."""
        service = MoveJobService(mock_conn)

        # Create job with custom config
        job = Job(
            id="test-job",
            file_id=42,
            file_path="/source/video.mkv",
            job_type=JobType.MOVE,
            status=JobStatus.RUNNING,
            priority=100,
            policy_name=None,
            policy_json=json.dumps(
                {
                    "destination_path": "/custom/dest.mkv",
                    "create_directories": False,
                    "overwrite": True,
                }
            ),
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00+00:00",
            started_at="2024-01-01T00:00:00+00:00",
        )

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("vpo.jobs.services.move.MoveExecutor") as mock_executor_cls,
            patch("vpo.jobs.services.move.update_file_path") as mock_update,
        ):
            mock_executor = MagicMock()
            mock_executor_cls.return_value = mock_executor
            mock_executor.create_plan.return_value = MagicMock()
            mock_executor.execute.return_value = MagicMock(
                success=True,
                source_path=Path("/source/video.mkv"),
                destination_path=Path("/custom/dest.mkv"),
                error_message=None,
            )
            mock_update.return_value = True

            service.process(job)

        # Verify executor was created with correct config
        mock_executor_cls.assert_called_once_with(
            create_directories=False,
            overwrite=True,
        )

    def test_process_rollback_on_db_failure(self, mock_conn, sample_move_job):
        """File rolled back when DB update fails."""
        service = MoveJobService(mock_conn)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("vpo.jobs.services.move.MoveExecutor") as mock_executor_cls,
            patch("vpo.jobs.services.move.update_file_path") as mock_update,
            patch("vpo.jobs.services.move.shutil.move") as mock_shutil_move,
        ):
            mock_executor = MagicMock()
            mock_executor_cls.return_value = mock_executor
            mock_executor.create_plan.return_value = MagicMock()
            mock_executor.execute.return_value = MagicMock(
                success=True,
                source_path=Path("/source/video.mkv"),
                destination_path=Path("/destination/video.mkv"),
                error_message=None,
            )
            # Simulate DB error
            mock_update.side_effect = sqlite3.Error("database is locked")

            result = service.process(sample_move_job)

        # Move should fail with rollback
        assert result.success is False
        assert "Database update failed" in result.error_message
        assert "rolled back" in result.error_message
        # Verify rollback was attempted
        mock_shutil_move.assert_called_once_with(
            "/destination/video.mkv", "/source/video.mkv"
        )

    def test_process_rollback_failure_logs_critical(self, mock_conn, sample_move_job):
        """Critical log when rollback fails."""
        service = MoveJobService(mock_conn)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("vpo.jobs.services.move.MoveExecutor") as mock_executor_cls,
            patch("vpo.jobs.services.move.update_file_path") as mock_update,
            patch("vpo.jobs.services.move.shutil.move") as mock_shutil_move,
            patch("vpo.jobs.services.move.logger") as mock_logger,
        ):
            mock_executor = MagicMock()
            mock_executor_cls.return_value = mock_executor
            mock_executor.create_plan.return_value = MagicMock()
            mock_executor.execute.return_value = MagicMock(
                success=True,
                source_path=Path("/source/video.mkv"),
                destination_path=Path("/destination/video.mkv"),
                error_message=None,
            )
            # Simulate DB error
            mock_update.side_effect = sqlite3.Error("database is locked")
            # Simulate rollback failure
            mock_shutil_move.side_effect = OSError("permission denied")

            result = service.process(sample_move_job)

        # Move should fail with critical error
        assert result.success is False
        assert "CRITICAL" in result.error_message
        assert "Rollback also failed" in result.error_message
        # Verify destination_path is included so user knows where file is
        assert result.destination_path == "/destination/video.mkv"
        # Verify critical was logged
        mock_logger.critical.assert_called_once()
