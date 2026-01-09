"""Unit tests for PhaseOutcome and SkipReason types.

T010: Tests for phase outcome tracking types introduced in conditional phases feature.
"""

import pytest

from vpo.policy.types import (
    PhaseOutcome,
    PhaseResult,
    SkipReason,
    SkipReasonType,
)


class TestPhaseOutcome:
    """Tests for PhaseOutcome enum."""

    def test_phase_outcome_values(self) -> None:
        """PhaseOutcome has expected values."""
        assert PhaseOutcome.PENDING.value == "pending"
        assert PhaseOutcome.COMPLETED.value == "completed"
        assert PhaseOutcome.FAILED.value == "failed"
        assert PhaseOutcome.SKIPPED.value == "skipped"

    def test_phase_outcome_members(self) -> None:
        """PhaseOutcome has exactly 4 members."""
        assert len(PhaseOutcome) == 4

    def test_phase_outcome_from_string(self) -> None:
        """PhaseOutcome can be looked up by value."""
        assert PhaseOutcome("pending") == PhaseOutcome.PENDING
        assert PhaseOutcome("completed") == PhaseOutcome.COMPLETED
        assert PhaseOutcome("failed") == PhaseOutcome.FAILED
        assert PhaseOutcome("skipped") == PhaseOutcome.SKIPPED


class TestSkipReasonType:
    """Tests for SkipReasonType enum."""

    def test_skip_reason_type_values(self) -> None:
        """SkipReasonType has expected values."""
        assert SkipReasonType.CONDITION.value == "condition"
        assert SkipReasonType.DEPENDENCY.value == "dependency"
        assert SkipReasonType.ERROR_MODE.value == "error_mode"
        assert SkipReasonType.RUN_IF.value == "run_if"

    def test_skip_reason_type_members(self) -> None:
        """SkipReasonType has exactly 4 members."""
        assert len(SkipReasonType) == 4


class TestSkipReason:
    """Tests for SkipReason dataclass."""

    def test_skip_reason_for_condition(self) -> None:
        """SkipReason captures condition skip correctly."""
        reason = SkipReason(
            reason_type=SkipReasonType.CONDITION,
            message="Phase 'transcode' skipped: video_codec matches [hevc, h265]",
            condition_name="video_codec",
            condition_value="hevc",
        )
        assert reason.reason_type == SkipReasonType.CONDITION
        assert "video_codec" in reason.message
        assert reason.condition_name == "video_codec"
        assert reason.condition_value == "hevc"
        assert reason.dependency_name is None
        assert reason.dependency_outcome is None

    def test_skip_reason_for_dependency(self) -> None:
        """SkipReason captures dependency skip correctly."""
        reason = SkipReason(
            reason_type=SkipReasonType.DEPENDENCY,
            message="Phase 'verify' skipped: dependency 'transcode' did not complete",
            dependency_name="transcode",
            dependency_outcome="skipped",
        )
        assert reason.reason_type == SkipReasonType.DEPENDENCY
        assert "transcode" in reason.message
        assert reason.dependency_name == "transcode"
        assert reason.dependency_outcome == "skipped"
        assert reason.condition_name is None

    def test_skip_reason_for_error_mode(self) -> None:
        """SkipReason captures error_mode skip correctly."""
        reason = SkipReason(
            reason_type=SkipReasonType.ERROR_MODE,
            message="Phase 'analyze' skipped due to on_error: skip after failure",
        )
        assert reason.reason_type == SkipReasonType.ERROR_MODE
        assert "on_error" in reason.message

    def test_skip_reason_for_run_if(self) -> None:
        """SkipReason captures run_if skip correctly."""
        reason = SkipReason(
            reason_type=SkipReasonType.RUN_IF,
            message="Phase 'verify' skipped: 'transcode' made no modifications",
            dependency_name="transcode",
        )
        assert reason.reason_type == SkipReasonType.RUN_IF
        assert "transcode" in reason.message
        assert reason.dependency_name == "transcode"

    def test_skip_reason_is_immutable(self) -> None:
        """SkipReason is frozen (immutable)."""
        reason = SkipReason(
            reason_type=SkipReasonType.CONDITION,
            message="Test message",
        )
        with pytest.raises(AttributeError):
            reason.message = "New message"  # type: ignore[misc]


class TestPhaseResultWithOutcome:
    """Tests for PhaseResult with outcome tracking."""

    def test_phase_result_default_outcome(self) -> None:
        """PhaseResult defaults to PENDING outcome."""
        result = PhaseResult(
            phase_name="test",
            success=True,
            duration_seconds=1.0,
            operations_executed=(),
            changes_made=0,
        )
        assert result.outcome == PhaseOutcome.PENDING

    def test_phase_result_with_completed_outcome(self) -> None:
        """PhaseResult can have COMPLETED outcome."""
        result = PhaseResult(
            phase_name="test",
            success=True,
            duration_seconds=1.0,
            operations_executed=("container",),
            changes_made=1,
            outcome=PhaseOutcome.COMPLETED,
            file_modified=True,
        )
        assert result.outcome == PhaseOutcome.COMPLETED
        assert result.file_modified is True
        assert result.skip_reason is None

    def test_phase_result_with_skipped_outcome(self) -> None:
        """PhaseResult can have SKIPPED outcome with reason."""
        skip_reason = SkipReason(
            reason_type=SkipReasonType.CONDITION,
            message="video_codec matches [hevc]",
            condition_name="video_codec",
            condition_value="hevc",
        )
        result = PhaseResult(
            phase_name="transcode",
            success=True,
            duration_seconds=0.01,
            operations_executed=(),
            changes_made=0,
            outcome=PhaseOutcome.SKIPPED,
            skip_reason=skip_reason,
            file_modified=False,
        )
        assert result.outcome == PhaseOutcome.SKIPPED
        assert result.skip_reason is not None
        assert result.skip_reason.reason_type == SkipReasonType.CONDITION
        assert result.file_modified is False

    def test_phase_result_with_failed_outcome(self) -> None:
        """PhaseResult can have FAILED outcome."""
        result = PhaseResult(
            phase_name="transcode",
            success=False,
            duration_seconds=5.0,
            operations_executed=("transcode",),
            changes_made=0,
            error="FFmpeg exited with code 1",
            outcome=PhaseOutcome.FAILED,
            file_modified=False,
        )
        assert result.outcome == PhaseOutcome.FAILED
        assert result.error is not None
        assert result.success is False

    def test_phase_result_file_modified_tracking(self) -> None:
        """PhaseResult tracks file_modified for run_if evaluation."""
        # Phase that modified file
        modified_result = PhaseResult(
            phase_name="transcode",
            success=True,
            duration_seconds=60.0,
            operations_executed=("transcode",),
            changes_made=1,
            outcome=PhaseOutcome.COMPLETED,
            file_modified=True,
        )
        assert modified_result.file_modified is True

        # Phase that made no changes
        unchanged_result = PhaseResult(
            phase_name="transcode",
            success=True,
            duration_seconds=0.1,
            operations_executed=(),
            changes_made=0,
            outcome=PhaseOutcome.SKIPPED,
            file_modified=False,
        )
        assert unchanged_result.file_modified is False
