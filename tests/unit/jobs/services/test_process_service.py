"""Unit tests for ProcessJobService."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.db.types import Job, JobStatus, JobType
from vpo.jobs.services.process import (
    ProcessJobResult,
    ProcessJobService,
)


@pytest.fixture
def test_job(tmp_path):
    """Create a test job with a real file."""
    test_file = tmp_path / "test.mkv"
    test_file.write_bytes(b"\x00" * 100)

    return Job(
        id="test-job-id",
        file_id=None,
        file_path=str(test_file),
        job_type=JobType.PROCESS,
        status=JobStatus.QUEUED,
        priority=100,
        policy_name="test_policy.yaml",
        policy_json=None,
        progress_percent=0.0,
        progress_json=None,
        created_at="2024-01-01T00:00:00Z",
    )


@pytest.fixture
def test_job_with_json(tmp_path):
    """Create a test job with embedded policy JSON."""
    test_file = tmp_path / "test.mkv"
    test_file.write_bytes(b"\x00" * 100)

    policy_data = {
        "schema_version": 13,
        "config": {
            "audio_languages": ["eng", "und"],
            "subtitle_languages": ["eng", "und"],
            "on_error": "fail",
        },
        "phases": [
            {
                "name": "apply",
                "track_order": ["video", "audio_main"],
            }
        ],
    }

    return Job(
        id="test-job-id",
        file_id=None,
        file_path=str(test_file),
        job_type=JobType.PROCESS,
        status=JobStatus.QUEUED,
        priority=100,
        policy_name=None,
        policy_json=json.dumps(policy_data),
        progress_percent=0.0,
        progress_json=None,
        created_at="2024-01-01T00:00:00Z",
    )


class TestProcessJobResult:
    """Tests for ProcessJobResult dataclass."""

    def test_result_defaults(self):
        """ProcessJobResult has proper defaults."""
        result = ProcessJobResult(success=True)

        assert result.success is True
        assert result.phases_completed == ()
        assert result.phases_failed == ()
        assert result.error_message is None

    def test_result_with_phases(self):
        """ProcessJobResult stores phase tuples."""
        result = ProcessJobResult(
            success=True,
            phases_completed=("analyze", "apply"),
            phases_failed=(),
        )

        assert result.phases_completed == ("analyze", "apply")
        assert len(result.phases_failed) == 0

    def test_result_is_frozen(self):
        """ProcessJobResult is immutable."""
        result = ProcessJobResult(success=True)

        with pytest.raises(AttributeError):
            result.success = False


class TestProcessJobServiceInit:
    """Tests for ProcessJobService initialization."""

    def test_init_with_connection(self, db_conn):
        """ProcessJobService initializes with database connection."""
        service = ProcessJobService(conn=db_conn)

        assert service.conn is db_conn


class TestProcessJobServiceProcess:
    """Tests for ProcessJobService.process() method."""

    def test_process_missing_file_returns_error(self, db_conn):
        """process() returns error when input file not found."""
        job = Job(
            id="test-job-id",
            file_id=None,
            file_path="/nonexistent/file.mkv",
            job_type=JobType.PROCESS,
            status=JobStatus.QUEUED,
            priority=100,
            policy_name="test.yaml",
            policy_json=None,
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00Z",
        )

        # Need to mock policy loading since file doesn't exist
        with patch.object(ProcessJobService, "_parse_policy") as mock_parse:
            mock_parse.return_value = (MagicMock(), None)

            service = ProcessJobService(conn=db_conn)
            result = service.process(job)

        assert result.success is False
        assert "not found" in result.error_message

    def test_process_no_policy_returns_error(self, db_conn, tmp_path):
        """process() returns error when no policy specified."""
        test_file = tmp_path / "test.mkv"
        test_file.write_bytes(b"\x00" * 100)

        job = Job(
            id="test-job-id",
            file_id=None,
            file_path=str(test_file),
            job_type=JobType.PROCESS,
            status=JobStatus.QUEUED,
            priority=100,
            policy_name=None,
            policy_json=None,
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00Z",
        )

        service = ProcessJobService(conn=db_conn)
        result = service.process(job)

        assert result.success is False
        assert "No policy specified" in result.error_message


class TestProcessJobServiceParsing:
    """Tests for policy parsing."""

    def test_parse_policy_from_json(self, db_conn, test_job_with_json):
        """_parse_policy parses embedded JSON policy."""
        service = ProcessJobService(conn=db_conn)

        policy, error = service._parse_policy(test_job_with_json, None)

        assert error is None
        assert policy is not None
        assert policy.schema_version == 13

    def test_parse_policy_from_name(self, db_conn, tmp_path):
        """_parse_policy loads policy from file path."""
        # Create a real policy file with phased format
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text("""schema_version: 13
config:
  audio_languages: [eng]
phases:
  - name: apply
""")

        job = Job(
            id="test-job-id",
            file_id=None,
            file_path=str(tmp_path / "test.mkv"),
            job_type=JobType.PROCESS,
            status=JobStatus.QUEUED,
            priority=100,
            policy_name=str(policy_file),
            policy_json=None,
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00Z",
        )

        service = ProcessJobService(conn=db_conn)
        policy, error = service._parse_policy(job, None)

        assert error is None
        assert policy is not None
        assert policy.schema_version == 13

    def test_parse_policy_missing_file_returns_error(self, db_conn, tmp_path):
        """_parse_policy returns error for missing policy file."""
        job = Job(
            id="test-job-id",
            file_id=None,
            file_path=str(tmp_path / "test.mkv"),
            job_type=JobType.PROCESS,
            status=JobStatus.QUEUED,
            priority=100,
            policy_name="/nonexistent/policy.yaml",
            policy_json=None,
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00Z",
        )

        service = ProcessJobService(conn=db_conn)
        policy, error = service._parse_policy(job, None)

        assert policy is None
        assert error is not None  # Any error message is acceptable


class TestProcessJobServiceTempFileCleanup:
    """Tests for temp file cleanup in policy parsing."""

    def test_temp_file_cleaned_up_on_success(self, db_conn, test_job_with_json):
        """Temp file is cleaned up after successful policy parsing."""
        service = ProcessJobService(conn=db_conn)

        # Track temp files created
        original_tempfile = tempfile.NamedTemporaryFile

        temp_files_created = []

        def tracking_tempfile(*args, **kwargs):
            result = original_tempfile(*args, **kwargs)
            temp_files_created.append(Path(result.name))
            return result

        with patch("tempfile.NamedTemporaryFile", tracking_tempfile):
            policy, error = service._parse_policy(test_job_with_json, None)

        assert error is None
        # Verify temp files were cleaned up
        for temp_file in temp_files_created:
            assert not temp_file.exists(), f"Temp file not cleaned: {temp_file}"

    def test_temp_file_cleaned_up_on_error(self, db_conn, tmp_path):
        """Temp file is cleaned up even when parsing fails."""
        # Create job with invalid JSON that will fail to parse
        job = Job(
            id="test-job-id",
            file_id=None,
            file_path=str(tmp_path / "test.mkv"),
            job_type=JobType.PROCESS,
            status=JobStatus.QUEUED,
            priority=100,
            policy_name=None,
            policy_json='{"schema_version": "invalid"}',  # Invalid type
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00Z",
        )

        service = ProcessJobService(conn=db_conn)

        # Track temp files created
        temp_files_created = []
        original_tempfile = tempfile.NamedTemporaryFile

        def tracking_tempfile(*args, **kwargs):
            result = original_tempfile(*args, **kwargs)
            temp_files_created.append(Path(result.name))
            return result

        with patch("tempfile.NamedTemporaryFile", tracking_tempfile):
            policy, error = service._parse_policy(job, None)

        # Parsing should fail
        assert policy is None or error is not None

        # But temp files should still be cleaned up
        for temp_file in temp_files_created:
            assert not temp_file.exists(), f"Temp file not cleaned: {temp_file}"


class TestProcessJobServiceWorkflowExecution:
    """Tests for workflow execution."""

    @patch("vpo.jobs.services.process.WorkflowRunner")
    def test_process_executes_workflow(
        self, mock_runner_cls, db_conn, test_job_with_json
    ):
        """process() creates and runs WorkflowRunner."""
        mock_runner = MagicMock()
        mock_run_result = MagicMock()
        mock_run_result.success = True
        mock_run_result.result.phase_results = []
        mock_run_result.result.error_message = None
        mock_runner.run_single.return_value = mock_run_result
        mock_runner_cls.for_daemon.return_value = mock_runner

        service = ProcessJobService(conn=db_conn)
        result = service.process(test_job_with_json)

        assert result.success is True
        mock_runner.run_single.assert_called_once()

    @patch("vpo.jobs.services.process.WorkflowRunner")
    def test_process_handles_workflow_failure(
        self, mock_runner_cls, db_conn, test_job_with_json
    ):
        """process() handles workflow failures gracefully."""
        mock_runner = MagicMock()
        mock_run_result = MagicMock()
        mock_run_result.success = False
        mock_run_result.result.phase_results = []
        mock_run_result.result.error_message = "Apply phase failed"
        mock_runner.run_single.return_value = mock_run_result
        mock_runner_cls.for_daemon.return_value = mock_runner

        service = ProcessJobService(conn=db_conn)
        result = service.process(test_job_with_json)

        assert result.success is False
        assert "Apply phase failed" in result.error_message

    @patch("vpo.jobs.services.process.WorkflowRunner")
    def test_process_handles_workflow_exception(
        self, mock_runner_cls, db_conn, test_job_with_json
    ):
        """process() handles exceptions from WorkflowRunner.

        Note: Exceptions are now caught inside WorkflowRunner.run_single,
        so this tests that the result error is properly propagated.
        """
        mock_runner = MagicMock()
        mock_run_result = MagicMock()
        mock_run_result.success = False
        mock_run_result.result.phase_results = []
        mock_run_result.result.error_message = "Unexpected error"
        mock_runner.run_single.return_value = mock_run_result
        mock_runner_cls.for_daemon.return_value = mock_runner

        service = ProcessJobService(conn=db_conn)
        result = service.process(test_job_with_json)

        assert result.success is False
        assert "Unexpected error" in result.error_message
