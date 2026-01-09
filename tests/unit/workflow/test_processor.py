"""Unit tests for WorkflowProcessor."""

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from vpo.db.schema import create_schema
from vpo.policy.models import (
    PolicySchema,
    ProcessingPhase,
    WorkflowConfig,
)
from vpo.workflow.processor import (
    FileProcessingResult,
    PhaseError,
    PhaseResult,
    WorkflowProcessor,
    WorkflowProgress,
)


@pytest.fixture
def db_conn():
    """Create in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    return conn


@pytest.fixture
def base_policy():
    """Create a minimal policy for testing."""
    return PolicySchema(
        schema_version=12,
        workflow=WorkflowConfig(
            phases=(ProcessingPhase.ANALYZE, ProcessingPhase.APPLY),
            on_error="fail",
        ),
    )


@pytest.fixture
def test_file(tmp_path):
    """Create a temporary test file."""
    f = tmp_path / "test.mkv"
    f.write_bytes(b"\x00" * 100)
    return f


class TestWorkflowProcessorInit:
    """Tests for WorkflowProcessor initialization."""

    def test_init_with_policy(self, db_conn, base_policy):
        """WorkflowProcessor initializes with policy workflow config."""
        processor = WorkflowProcessor(
            conn=db_conn,
            policy=base_policy,
            dry_run=False,
            verbose=False,
        )

        assert processor.conn is db_conn
        assert processor.policy is base_policy
        assert processor.dry_run is False
        assert processor.verbose is False
        assert len(processor.config.phases) == 2

    def test_init_without_workflow_defaults_to_apply(self, db_conn):
        """WorkflowProcessor defaults to APPLY phase when no workflow config."""
        policy = PolicySchema(schema_version=12)

        processor = WorkflowProcessor(
            conn=db_conn,
            policy=policy,
        )

        assert processor.config.phases == (ProcessingPhase.APPLY,)

    def test_init_with_policy_name(self, db_conn, base_policy):
        """WorkflowProcessor accepts policy_name for audit tracking."""
        processor = WorkflowProcessor(
            conn=db_conn,
            policy=base_policy,
            policy_name="test_policy.yaml",
        )

        assert processor.policy_name == "test_policy.yaml"

    def test_init_with_progress_callback(self, db_conn, base_policy):
        """WorkflowProcessor accepts progress callback."""
        callback = MagicMock()
        processor = WorkflowProcessor(
            conn=db_conn,
            policy=base_policy,
            progress_callback=callback,
        )

        assert processor.progress_callback is callback


class TestWorkflowProcessorPhaseExecution:
    """Tests for phase execution logic."""

    @patch("vpo.workflow.phases.analyze.AnalyzePhase")
    @patch("vpo.workflow.phases.apply.ApplyPhase")
    def test_process_file_runs_phases_in_order(
        self, mock_apply_cls, mock_analyze_cls, db_conn, test_file
    ):
        """process_file runs phases in the order defined in config."""
        mock_analyze = MagicMock()
        mock_analyze.run.return_value = 0
        mock_analyze_cls.return_value = mock_analyze

        mock_apply = MagicMock()
        mock_apply.run.return_value = 1
        mock_apply_cls.return_value = mock_apply

        policy = PolicySchema(
            schema_version=12,
            workflow=WorkflowConfig(
                phases=(ProcessingPhase.ANALYZE, ProcessingPhase.APPLY),
            ),
        )

        processor = WorkflowProcessor(conn=db_conn, policy=policy)
        result = processor.process_file(test_file)

        assert result.success is True
        assert ProcessingPhase.ANALYZE in result.phases_completed
        assert ProcessingPhase.APPLY in result.phases_completed
        assert len(result.phases_failed) == 0

    @patch("vpo.workflow.phases.apply.ApplyPhase")
    def test_process_file_handles_phase_failure(
        self, mock_apply_cls, db_conn, test_file
    ):
        """process_file handles phase failures according to on_error policy."""
        mock_apply = MagicMock()
        mock_apply.run.side_effect = PhaseError(ProcessingPhase.APPLY, "Test error")
        mock_apply_cls.return_value = mock_apply

        policy = PolicySchema(
            schema_version=12,
            workflow=WorkflowConfig(
                phases=(ProcessingPhase.APPLY, ProcessingPhase.TRANSCODE),
                on_error="fail",
            ),
        )

        processor = WorkflowProcessor(conn=db_conn, policy=policy)
        result = processor.process_file(test_file)

        assert result.success is False
        assert ProcessingPhase.APPLY in result.phases_failed
        assert ProcessingPhase.TRANSCODE in result.phases_skipped

    @patch("vpo.workflow.phases.apply.ApplyPhase")
    def test_process_file_on_error_continue(self, mock_apply_cls, db_conn, test_file):
        """on_error=continue proceeds to next phase despite failure."""
        mock_apply = MagicMock()
        mock_apply.run.side_effect = PhaseError(ProcessingPhase.APPLY, "Test error")
        mock_apply_cls.return_value = mock_apply

        policy = PolicySchema(
            schema_version=12,
            workflow=WorkflowConfig(
                phases=(ProcessingPhase.APPLY,),
                on_error="continue",
            ),
        )

        processor = WorkflowProcessor(conn=db_conn, policy=policy)
        result = processor.process_file(test_file)

        # With continue, the workflow completes (with failures)
        assert ProcessingPhase.APPLY in result.phases_failed
        assert len(result.phases_skipped) == 0


class TestWorkflowProcessorDatabaseHandling:
    """Tests for database transaction handling."""

    @patch("vpo.workflow.phases.apply.ApplyPhase")
    def test_rollback_on_sqlite_error(self, mock_apply_cls, db_conn, test_file):
        """Database errors trigger rollback and are handled properly."""
        mock_apply = MagicMock()
        mock_apply.run.side_effect = sqlite3.Error("Test DB error")
        mock_apply_cls.return_value = mock_apply

        policy = PolicySchema(
            schema_version=12,
            workflow=WorkflowConfig(
                phases=(ProcessingPhase.APPLY,),
                on_error="fail",  # Explicitly set to fail so result.success=False
            ),
        )

        processor = WorkflowProcessor(conn=db_conn, policy=policy)
        result = processor.process_file(test_file)

        # Verify the error was handled and result reflects failure
        assert result.success is False
        assert "Database error" in result.error_message
        assert ProcessingPhase.APPLY in result.phases_failed


class TestWorkflowProcessorProgress:
    """Tests for progress callback handling."""

    @patch("vpo.workflow.phases.apply.ApplyPhase")
    def test_progress_callback_called(self, mock_apply_cls, db_conn, test_file):
        """Progress callback is called for each phase."""
        mock_apply = MagicMock()
        mock_apply.run.return_value = 0
        mock_apply_cls.return_value = mock_apply

        progress_updates = []

        def progress_callback(progress: WorkflowProgress):
            progress_updates.append(progress)

        policy = PolicySchema(
            schema_version=12,
            workflow=WorkflowConfig(phases=(ProcessingPhase.APPLY,)),
        )

        processor = WorkflowProcessor(
            conn=db_conn,
            policy=policy,
            progress_callback=progress_callback,
        )
        processor.process_file(test_file)

        assert len(progress_updates) == 1
        assert progress_updates[0].current_phase == ProcessingPhase.APPLY
        assert progress_updates[0].phase_index == 0
        assert progress_updates[0].total_phases == 1


class TestPhaseResult:
    """Tests for PhaseResult dataclass."""

    def test_phase_result_defaults(self):
        """PhaseResult has sensible defaults."""
        result = PhaseResult(phase=ProcessingPhase.APPLY, success=True)

        assert result.message is None
        assert result.duration_seconds == 0.0
        assert result.changes_made == 0


class TestFileProcessingResult:
    """Tests for FileProcessingResult dataclass."""

    def test_summary_success(self, tmp_path):
        """Summary shows completed phases on success."""
        result = FileProcessingResult(
            file_path=tmp_path / "test.mkv",
            success=True,
            phases_completed=[ProcessingPhase.ANALYZE, ProcessingPhase.APPLY],
        )

        assert "Completed phases: analyze, apply" in result.summary

    def test_summary_failure(self, tmp_path):
        """Summary shows failed phases and error on failure."""
        result = FileProcessingResult(
            file_path=tmp_path / "test.mkv",
            success=False,
            phases_failed=[ProcessingPhase.APPLY],
            error_message="Test error",
        )

        assert "Failed phases: apply" in result.summary
        assert "Test error" in result.summary


class TestWorkflowProgress:
    """Tests for WorkflowProgress dataclass."""

    def test_overall_progress_calculation(self, tmp_path):
        """overall_progress calculates correctly."""
        progress = WorkflowProgress(
            file_path=tmp_path / "test.mkv",
            current_phase=ProcessingPhase.APPLY,
            phase_index=1,
            total_phases=2,
            phase_progress=0.5,
        )

        # Base: 1/2 = 50%, phase contribution: 0.5/2 = 25%
        assert progress.overall_progress == 75.0

    def test_overall_progress_zero_phases(self, tmp_path):
        """overall_progress handles zero phases."""
        progress = WorkflowProgress(
            file_path=tmp_path / "test.mkv",
            current_phase=ProcessingPhase.APPLY,
            phase_index=0,
            total_phases=0,
        )

        assert progress.overall_progress == 0.0
