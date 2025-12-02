"""Unit tests for TranscodePhase."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from video_policy_orchestrator.db.schema import create_schema
from video_policy_orchestrator.executor.transcode import TranscodeResult
from video_policy_orchestrator.policy.models import (
    PolicySchema,
    ProcessingPhase,
    TranscodePolicyConfig,
)
from video_policy_orchestrator.workflow.phases.transcode import TranscodePhase
from video_policy_orchestrator.workflow.processor import PhaseError


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
    return PolicySchema(schema_version=12)


@pytest.fixture
def policy_with_transcode():
    """Create a policy with transcode config."""
    return PolicySchema(
        schema_version=12,
        transcode=TranscodePolicyConfig(
            target_video_codec="hevc",
        ),
    )


@pytest.fixture
def test_file(tmp_path):
    """Create a temporary test file."""
    f = tmp_path / "test.mkv"
    f.write_bytes(b"\x00" * 100)
    return f


def insert_test_file(conn, file_path: Path) -> int:
    """Insert a test file record and return its ID."""
    cursor = conn.execute(
        """
        INSERT INTO files (
            path, filename, directory, extension, size_bytes,
            container_format, modified_at, scanned_at, scan_status
        )
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), 'complete')
        """,
        (
            str(file_path),
            file_path.name,
            str(file_path.parent),
            file_path.suffix,
            1000000,
            "mkv",
        ),
    )
    conn.commit()
    return cursor.lastrowid


def insert_test_track(
    conn,
    file_id: int,
    track_type: str = "video",
    codec: str = "h264",
    width: int | None = 1920,
    height: int | None = 1080,
) -> int:
    """Insert a test track record and return its ID."""
    cursor = conn.execute(
        """
        INSERT INTO tracks (
            file_id, track_index, track_type, codec, language,
            width, height
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (file_id, 0, track_type, codec, "eng", width, height),
    )
    conn.commit()
    return cursor.lastrowid


class TestTranscodePhaseInit:
    """Tests for TranscodePhase initialization."""

    def test_init_with_defaults(self, db_conn, base_policy):
        """TranscodePhase initializes with default values."""
        phase = TranscodePhase(conn=db_conn, policy=base_policy)

        assert phase.conn is db_conn
        assert phase.policy is base_policy
        assert phase.dry_run is False
        assert phase.verbose is False


class TestTranscodePhaseRun:
    """Tests for TranscodePhase.run() method."""

    def test_run_skips_without_transcode_config(self, db_conn, base_policy, test_file):
        """run() returns 0 when no transcode config."""
        phase = TranscodePhase(conn=db_conn, policy=base_policy)

        changes = phase.run(test_file)

        assert changes == 0

    def test_run_raises_for_missing_file(
        self, db_conn, policy_with_transcode, test_file
    ):
        """run() raises PhaseError when file not in database."""
        phase = TranscodePhase(conn=db_conn, policy=policy_with_transcode)

        with pytest.raises(PhaseError) as exc_info:
            phase.run(test_file)

        assert "not found in database" in str(exc_info.value)
        assert exc_info.value.phase == ProcessingPhase.TRANSCODE

    def test_run_skips_without_video_track(
        self, db_conn, policy_with_transcode, test_file
    ):
        """run() returns 0 when no video track found."""
        file_id = insert_test_file(db_conn, test_file)
        insert_test_track(db_conn, file_id, track_type="audio", codec="aac")

        phase = TranscodePhase(conn=db_conn, policy=policy_with_transcode)

        changes = phase.run(test_file)

        assert changes == 0

    @patch("video_policy_orchestrator.executor.transcode.TranscodeExecutor")
    def test_run_skips_when_plan_says_skip(
        self, mock_executor_cls, db_conn, policy_with_transcode, test_file
    ):
        """run() returns 0 when transcode plan has skip_reason."""
        file_id = insert_test_file(db_conn, test_file)
        insert_test_track(db_conn, file_id)

        mock_executor = MagicMock()
        mock_plan = MagicMock()
        mock_plan.skip_reason = "Already HEVC"
        mock_executor.create_plan.return_value = mock_plan
        mock_executor_cls.return_value = mock_executor

        phase = TranscodePhase(conn=db_conn, policy=policy_with_transcode)

        changes = phase.run(test_file)

        assert changes == 0
        mock_executor.execute.assert_not_called()


class TestTranscodePhaseDryRun:
    """Tests for dry-run mode."""

    @patch("video_policy_orchestrator.executor.transcode.TranscodeExecutor")
    def test_dry_run_does_not_execute(
        self, mock_executor_cls, db_conn, policy_with_transcode, test_file
    ):
        """dry_run=True creates plan but does not execute."""
        file_id = insert_test_file(db_conn, test_file)
        insert_test_track(db_conn, file_id)

        mock_executor = MagicMock()
        mock_plan = MagicMock()
        mock_plan.skip_reason = None
        mock_executor.create_plan.return_value = mock_plan
        mock_executor_cls.return_value = mock_executor

        phase = TranscodePhase(conn=db_conn, policy=policy_with_transcode, dry_run=True)

        changes = phase.run(test_file)

        assert changes == 1
        mock_executor.execute.assert_not_called()


class TestTranscodePhaseExecution:
    """Tests for transcode execution."""

    @patch("video_policy_orchestrator.executor.transcode.TranscodeExecutor")
    def test_execute_success(
        self, mock_executor_cls, db_conn, policy_with_transcode, test_file
    ):
        """Successful transcode returns 1 change."""
        file_id = insert_test_file(db_conn, test_file)
        insert_test_track(db_conn, file_id)

        mock_executor = MagicMock()
        mock_plan = MagicMock()
        mock_plan.skip_reason = None
        mock_executor.create_plan.return_value = mock_plan

        mock_result = MagicMock(spec=TranscodeResult)
        mock_result.success = True
        mock_executor.execute.return_value = mock_result
        mock_executor_cls.return_value = mock_executor

        phase = TranscodePhase(conn=db_conn, policy=policy_with_transcode)

        changes = phase.run(test_file)

        assert changes == 1
        mock_executor.execute.assert_called_once_with(mock_plan)

    @patch("video_policy_orchestrator.executor.transcode.TranscodeExecutor")
    def test_execute_failure_raises_phase_error(
        self, mock_executor_cls, db_conn, policy_with_transcode, test_file
    ):
        """Failed transcode raises PhaseError."""
        file_id = insert_test_file(db_conn, test_file)
        insert_test_track(db_conn, file_id)

        mock_executor = MagicMock()
        mock_plan = MagicMock()
        mock_plan.skip_reason = None
        mock_executor.create_plan.return_value = mock_plan

        mock_result = MagicMock(spec=TranscodeResult)
        mock_result.success = False
        mock_result.error_message = "FFmpeg error"
        mock_executor.execute.return_value = mock_result
        mock_executor_cls.return_value = mock_executor

        phase = TranscodePhase(conn=db_conn, policy=policy_with_transcode)

        with pytest.raises(PhaseError) as exc_info:
            phase.run(test_file)

        assert "Transcode failed" in str(exc_info.value)
        assert "FFmpeg error" in str(exc_info.value)
        assert exc_info.value.phase == ProcessingPhase.TRANSCODE

    @patch("video_policy_orchestrator.executor.transcode.TranscodeExecutor")
    def test_execute_exception_wrapped_in_phase_error(
        self, mock_executor_cls, db_conn, policy_with_transcode, test_file
    ):
        """Exceptions during transcode are wrapped in PhaseError."""
        file_id = insert_test_file(db_conn, test_file)
        insert_test_track(db_conn, file_id)

        mock_executor = MagicMock()
        mock_plan = MagicMock()
        mock_plan.skip_reason = None
        mock_executor.create_plan.return_value = mock_plan
        mock_executor.execute.side_effect = RuntimeError("Unexpected error")
        mock_executor_cls.return_value = mock_executor

        phase = TranscodePhase(conn=db_conn, policy=policy_with_transcode)

        with pytest.raises(PhaseError) as exc_info:
            phase.run(test_file)

        assert "Transcode failed" in str(exc_info.value)
        assert exc_info.value.cause is not None


class TestTranscodePhaseHelpers:
    """Tests for helper methods."""

    def test_has_transcode_config_with_transcode(self, db_conn, policy_with_transcode):
        """_has_transcode_config returns True with transcode config."""
        phase = TranscodePhase(conn=db_conn, policy=policy_with_transcode)

        assert phase._has_transcode_config() is True

    def test_has_transcode_config_without_transcode(self, db_conn, base_policy):
        """_has_transcode_config returns False without transcode config."""
        phase = TranscodePhase(conn=db_conn, policy=base_policy)

        assert phase._has_transcode_config() is False
