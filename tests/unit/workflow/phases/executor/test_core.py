"""Unit tests for workflow/phases/executor/core.py.

Tests the core operation execution functions:
- execute_operation: Main entry point with timing and error handling
- dispatch_operation: Routes operation types to their specific handlers
"""

from unittest.mock import MagicMock, patch

import pytest

from vpo.db.types import TrackInfo
from vpo.policy.exceptions import PolicyError
from vpo.policy.types import (
    GlobalConfig,
    OnErrorMode,
    OperationType,
    PhaseDefinition,
    PolicySchema,
)
from vpo.workflow.phases.executor.core import dispatch_operation, execute_operation
from vpo.workflow.phases.executor.types import OperationResult, PhaseExecutionState


@pytest.fixture
def test_file(tmp_path):
    """Create a temporary test file."""
    f = tmp_path / "test.mkv"
    f.write_bytes(b"\x00" * 100)
    return f


@pytest.fixture
def global_config():
    """Create a GlobalConfig for testing."""
    return GlobalConfig(
        audio_language_preference=("eng", "und"),
        subtitle_language_preference=("eng",),
        commentary_patterns=("commentary", "director"),
        on_error=OnErrorMode.CONTINUE,
    )


@pytest.fixture
def policy(global_config):
    """Create a PolicySchema for testing."""
    return PolicySchema(
        schema_version=12,
        config=global_config,
        phases=(PhaseDefinition(name="test"),),
    )


@pytest.fixture
def mock_file_info(test_file):
    """Create a mock FileInfo object."""
    mock = MagicMock()
    mock.path = test_file
    mock.container_format = "mkv"
    mock.tracks = [
        TrackInfo(index=0, track_type="video", codec="h264"),
        TrackInfo(index=1, track_type="audio", codec="aac", language="eng"),
    ]
    return mock


@pytest.fixture
def phase_state(test_file):
    """Create a PhaseExecutionState for testing."""
    phase = PhaseDefinition(name="test")
    return PhaseExecutionState(file_path=test_file, phase=phase)


@pytest.fixture
def tools():
    """Create a mock tools dictionary."""
    return {"ffmpeg": True, "mkvpropedit": True, "mkvmerge": True}


# =============================================================================
# Tests for execute_operation
# =============================================================================


class TestExecuteOperation:
    """Tests for the execute_operation function."""

    def test_returns_success_on_handler_success(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """Successful handler execution returns OperationResult with success=True."""
        with patch(
            "vpo.workflow.phases.executor.core.dispatch_operation"
        ) as mock_dispatch:
            mock_dispatch.return_value = 2

            result = execute_operation(
                op_type=OperationType.CONTAINER,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=True,
                tools=tools,
                plugin_registry=None,
            )

        assert isinstance(result, OperationResult)
        assert result.success is True
        assert result.changes_made == 2
        assert result.operation == OperationType.CONTAINER
        assert result.constraint_skipped is False
        assert result.message is None

    def test_captures_timing_accurately(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """Operation duration is captured in the result."""
        with patch(
            "vpo.workflow.phases.executor.core.dispatch_operation"
        ) as mock_dispatch:
            mock_dispatch.return_value = 0

            result = execute_operation(
                op_type=OperationType.AUDIO_FILTER,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=True,
                tools=tools,
                plugin_registry=None,
            )

        # Duration should be non-negative and reasonable (< 1 second for mocked call)
        assert result.duration_seconds >= 0.0
        assert result.duration_seconds < 1.0

    def test_returns_success_on_policy_error(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """PolicyError returns success=True with constraint_skipped=True."""
        with patch(
            "vpo.workflow.phases.executor.core.dispatch_operation"
        ) as mock_dispatch:
            mock_dispatch.side_effect = PolicyError("No matching tracks found")

            result = execute_operation(
                op_type=OperationType.SUBTITLE_FILTER,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=False,
                tools=tools,
                plugin_registry=None,
            )

        # PolicyError is NOT a failure - it means the policy is working correctly
        assert result.success is True
        assert result.constraint_skipped is True
        assert result.changes_made == 0
        assert "No matching tracks found" in result.message
        assert result.operation == OperationType.SUBTITLE_FILTER

    def test_sets_constraint_skipped_flag_on_policy_error(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """PolicyError sets constraint_skipped flag to True."""
        with patch(
            "vpo.workflow.phases.executor.core.dispatch_operation"
        ) as mock_dispatch:
            mock_dispatch.side_effect = PolicyError("Track constraint violated")

            result = execute_operation(
                op_type=OperationType.TRACK_ORDER,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=False,
                tools=tools,
                plugin_registry=None,
            )

        assert result.constraint_skipped is True

    def test_returns_failure_on_generic_exception(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """Generic exception returns success=False with error message."""
        with patch(
            "vpo.workflow.phases.executor.core.dispatch_operation"
        ) as mock_dispatch:
            mock_dispatch.side_effect = RuntimeError("FFmpeg crashed unexpectedly")

            result = execute_operation(
                op_type=OperationType.TRANSCODE,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=False,
                tools=tools,
                plugin_registry=None,
            )

        assert result.success is False
        assert result.constraint_skipped is False
        assert result.changes_made == 0
        assert "FFmpeg crashed unexpectedly" in result.message
        assert result.operation == OperationType.TRANSCODE

    def test_timing_captured_even_on_exception(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """Duration is captured even when an exception occurs."""
        with patch(
            "vpo.workflow.phases.executor.core.dispatch_operation"
        ) as mock_dispatch:
            mock_dispatch.side_effect = ValueError("Invalid parameter")

            result = execute_operation(
                op_type=OperationType.DEFAULT_FLAGS,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=False,
                tools=tools,
                plugin_registry=None,
            )

        assert result.duration_seconds >= 0.0


# =============================================================================
# Tests for dispatch_operation
# =============================================================================


class TestDispatchOperation:
    """Tests for the dispatch_operation function."""

    def test_dispatches_container_operation(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """CONTAINER operation routes to execute_container handler."""
        with patch(
            "vpo.workflow.phases.executor.core.execute_container"
        ) as mock_handler:
            mock_handler.return_value = 1

            result = dispatch_operation(
                op_type=OperationType.CONTAINER,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=True,
                tools=tools,
                plugin_registry=None,
            )

        mock_handler.assert_called_once()
        assert result == 1

    def test_dispatches_audio_filter_operation(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """AUDIO_FILTER operation routes to execute_audio_filter handler."""
        with patch(
            "vpo.workflow.phases.executor.core.execute_audio_filter"
        ) as mock_handler:
            mock_handler.return_value = 3

            result = dispatch_operation(
                op_type=OperationType.AUDIO_FILTER,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=True,
                tools=tools,
                plugin_registry=None,
            )

        mock_handler.assert_called_once()
        assert result == 3

    def test_dispatches_subtitle_filter_operation(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """SUBTITLE_FILTER operation routes to execute_subtitle_filter handler."""
        with patch(
            "vpo.workflow.phases.executor.core.execute_subtitle_filter"
        ) as mock_handler:
            mock_handler.return_value = 2

            result = dispatch_operation(
                op_type=OperationType.SUBTITLE_FILTER,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=True,
                tools=tools,
                plugin_registry=None,
            )

        mock_handler.assert_called_once()
        assert result == 2

    def test_dispatches_attachment_filter_operation(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """ATTACHMENT_FILTER operation routes to execute_attachment_filter handler."""
        with patch(
            "vpo.workflow.phases.executor.core.execute_attachment_filter"
        ) as mock_handler:
            mock_handler.return_value = 1

            result = dispatch_operation(
                op_type=OperationType.ATTACHMENT_FILTER,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=True,
                tools=tools,
                plugin_registry=None,
            )

        mock_handler.assert_called_once()
        assert result == 1

    def test_dispatches_track_order_operation(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """TRACK_ORDER operation routes to execute_track_order handler."""
        with patch(
            "vpo.workflow.phases.executor.core.execute_track_order"
        ) as mock_handler:
            mock_handler.return_value = 4

            result = dispatch_operation(
                op_type=OperationType.TRACK_ORDER,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=True,
                tools=tools,
                plugin_registry=None,
            )

        mock_handler.assert_called_once()
        assert result == 4

    def test_dispatches_default_flags_operation(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """DEFAULT_FLAGS operation routes to execute_default_flags handler."""
        with patch(
            "vpo.workflow.phases.executor.core.execute_default_flags"
        ) as mock_handler:
            mock_handler.return_value = 2

            result = dispatch_operation(
                op_type=OperationType.DEFAULT_FLAGS,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=True,
                tools=tools,
                plugin_registry=None,
            )

        mock_handler.assert_called_once()
        assert result == 2

    def test_dispatches_conditional_operation(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """CONDITIONAL operation routes to execute_conditional handler."""
        with patch(
            "vpo.workflow.phases.executor.core.execute_conditional"
        ) as mock_handler:
            mock_handler.return_value = 0

            result = dispatch_operation(
                op_type=OperationType.CONDITIONAL,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=True,
                tools=tools,
                plugin_registry=None,
            )

        mock_handler.assert_called_once()
        assert result == 0

    def test_dispatches_transcode_operation(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """TRANSCODE operation routes to execute_transcode handler."""
        with patch(
            "vpo.workflow.phases.executor.core.execute_transcode"
        ) as mock_handler:
            mock_handler.return_value = 1

            result = dispatch_operation(
                op_type=OperationType.TRANSCODE,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=True,
                tools=tools,
                plugin_registry=None,
            )

        mock_handler.assert_called_once()
        # Transcode handler receives fewer arguments
        call_args = mock_handler.call_args
        assert call_args[0][0] is phase_state  # state
        assert result == 1

    def test_dispatches_audio_synthesis_operation(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """AUDIO_SYNTHESIS operation routes to execute_audio_synthesis handler."""
        with patch(
            "vpo.workflow.phases.executor.core.execute_audio_synthesis"
        ) as mock_handler:
            mock_handler.return_value = 2

            result = dispatch_operation(
                op_type=OperationType.AUDIO_SYNTHESIS,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=False,
                tools=tools,
                plugin_registry=None,
            )

        mock_handler.assert_called_once()
        assert result == 2

    def test_dispatches_file_timestamp_operation(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """FILE_TIMESTAMP operation routes to execute_file_timestamp handler."""
        with patch(
            "vpo.workflow.phases.executor.core.execute_file_timestamp"
        ) as mock_handler:
            mock_handler.return_value = 1

            result = dispatch_operation(
                op_type=OperationType.FILE_TIMESTAMP,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=False,
                tools=tools,
                plugin_registry=None,
            )

        mock_handler.assert_called_once()
        assert result == 1

    def test_dispatches_transcription_operation(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """TRANSCRIPTION operation routes to execute_transcription handler."""
        mock_registry = MagicMock()

        with patch(
            "vpo.workflow.phases.executor.core.execute_transcription"
        ) as mock_handler:
            mock_handler.return_value = 1

            result = dispatch_operation(
                op_type=OperationType.TRANSCRIPTION,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=False,
                tools=tools,
                plugin_registry=mock_registry,
            )

        mock_handler.assert_called_once()
        # Verify plugin_registry is passed to transcription handler
        call_args = mock_handler.call_args
        assert call_args[0][-1] is mock_registry  # Last arg is plugin_registry
        assert result == 1

    def test_returns_zero_for_unknown_operation_type(
        self, phase_state, mock_file_info, db_conn, policy, tools, caplog
    ):
        """Unknown operation type returns 0 and logs warning."""
        # Create a mock operation type that won't match any handler
        unknown_op = MagicMock()
        unknown_op.value = "UNKNOWN_OP"

        with patch(
            "vpo.workflow.phases.executor.core.execute_container"
        ):  # Ensure handlers exist
            result = dispatch_operation(
                op_type=unknown_op,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=True,
                tools=tools,
                plugin_registry=None,
            )

        assert result == 0

    def test_plan_args_passed_correctly_to_plan_handlers(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """Plan-based handlers receive correct arguments tuple."""
        with patch(
            "vpo.workflow.phases.executor.core.execute_audio_filter"
        ) as mock_handler:
            mock_handler.return_value = 0

            dispatch_operation(
                op_type=OperationType.AUDIO_FILTER,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=True,
                tools=tools,
                plugin_registry=None,
            )

        # Verify all plan_args are passed correctly
        call_args = mock_handler.call_args[0]  # Positional args
        assert call_args[0] is phase_state
        assert call_args[1] is mock_file_info
        assert call_args[2] is db_conn
        assert call_args[3] is policy
        assert call_args[4] is True  # dry_run
        assert call_args[5] is tools

    def test_transcode_receives_reduced_arguments(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """Transcode handler receives only state, file_info, conn, dry_run."""
        with patch(
            "vpo.workflow.phases.executor.core.execute_transcode"
        ) as mock_handler:
            mock_handler.return_value = 0

            dispatch_operation(
                op_type=OperationType.TRANSCODE,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=True,
                tools=tools,
                plugin_registry=None,
            )

        # Transcode receives fewer args than plan operations
        call_args = mock_handler.call_args[0]
        assert len(call_args) == 4
        assert call_args[0] is phase_state
        assert call_args[1] is mock_file_info
        assert call_args[2] is db_conn
        assert call_args[3] is True  # dry_run


# =============================================================================
# Integration-style tests (testing execute_operation + dispatch together)
# =============================================================================


class TestExecuteOperationIntegration:
    """Integration tests for execute_operation with real handlers (mocked)."""

    def test_full_flow_container_success(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """Full flow from execute_operation through dispatch to handler."""
        with patch(
            "vpo.workflow.phases.executor.core.execute_container"
        ) as mock_handler:
            mock_handler.return_value = 1

            result = execute_operation(
                op_type=OperationType.CONTAINER,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=False,
                tools=tools,
                plugin_registry=None,
            )

        assert result.success is True
        assert result.changes_made == 1
        assert result.operation == OperationType.CONTAINER
        mock_handler.assert_called_once()

    def test_full_flow_handler_raises_policy_error(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """Handler raising PolicyError results in constraint_skipped=True."""
        with patch(
            "vpo.workflow.phases.executor.core.execute_audio_filter"
        ) as mock_handler:
            mock_handler.side_effect = PolicyError("No English audio tracks")

            result = execute_operation(
                op_type=OperationType.AUDIO_FILTER,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=False,
                tools=tools,
                plugin_registry=None,
            )

        assert result.success is True
        assert result.constraint_skipped is True
        assert "No English audio" in result.message

    def test_full_flow_handler_raises_runtime_error(
        self, phase_state, mock_file_info, db_conn, policy, tools
    ):
        """Handler raising RuntimeError results in success=False."""
        with patch(
            "vpo.workflow.phases.executor.core.execute_transcode"
        ) as mock_handler:
            mock_handler.side_effect = RuntimeError("Out of disk space")

            result = execute_operation(
                op_type=OperationType.TRANSCODE,
                state=phase_state,
                file_info=mock_file_info,
                conn=db_conn,
                policy=policy,
                dry_run=False,
                tools=tools,
                plugin_registry=None,
            )

        assert result.success is False
        assert result.constraint_skipped is False
        assert "Out of disk space" in result.message
