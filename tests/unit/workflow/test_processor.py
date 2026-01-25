"""Unit tests for workflow/processor.py.

Tests the WorkflowProcessor class:
- Phase execution order and orchestration
- Skip condition evaluation (skip_when, depends_on, run_if)
- Error mode handling (on_error: skip, continue, fail)
- Re-introspection after file modifications
"""

import sqlite3
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from vpo.db.schema import create_schema
from vpo.db.types import FileInfo, TrackInfo
from vpo.policy.types import (
    GlobalConfig,
    OnErrorMode,
    PhaseDefinition,
    PhaseExecutionError,
    PhaseOutcome,
    PhaseResult,
    PhaseSkipCondition,
    PolicySchema,
    RunIfCondition,
)
from vpo.workflow.processor import WorkflowProcessor


@pytest.fixture
def db_conn():
    """Create in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def test_file(tmp_path):
    """Create a temporary test file."""
    f = tmp_path / "test.mkv"
    f.write_bytes(b"\x00" * 1000)
    return f


@pytest.fixture
def sample_file_info(test_file):
    """Create sample FileInfo for testing."""
    return FileInfo(
        path=test_file,
        filename=test_file.name,
        directory=test_file.parent,
        extension=".mkv",
        size_bytes=1000,
        modified_at=datetime.now(timezone.utc),
        content_hash="abc123",
        container_format="matroska",
        tracks=(
            TrackInfo(
                index=0,
                track_type="video",
                codec="h264",
                width=1920,
                height=1080,
            ),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                channels=2,
                language="eng",
            ),
        ),
    )


@pytest.fixture
def make_policy():
    """Factory for creating PolicySchema with custom phases."""

    def _make(
        phases: list[PhaseDefinition] | None = None,
        on_error: OnErrorMode = OnErrorMode.CONTINUE,
    ) -> PolicySchema:
        if phases is None:
            phases = [PhaseDefinition(name="default")]
        return PolicySchema(
            schema_version=12,
            config=GlobalConfig(on_error=on_error),
            phases=tuple(phases),
        )

    return _make


@pytest.fixture
def make_phase_result():
    """Factory for creating PhaseResult objects."""

    def _make(
        phase_name: str = "test",
        success: bool = True,
        changes_made: int = 0,
        duration_seconds: float = 0.1,
        message: str | None = None,
        error: str | None = None,
    ) -> PhaseResult:
        return PhaseResult(
            phase_name=phase_name,
            success=success,
            changes_made=changes_made,
            duration_seconds=duration_seconds,
            operations_executed=(),
            message=message,
            error=error,
            outcome=PhaseOutcome.COMPLETED if success else PhaseOutcome.FAILED,
            file_modified=changes_made > 0,
        )

    return _make


# =============================================================================
# Tests for process_file phase execution
# =============================================================================


class TestProcessFilePhaseExecution:
    """Tests for phase execution order and basic flow."""

    def test_executes_phases_in_order(
        self, db_conn, test_file, make_policy, make_phase_result, sample_file_info
    ):
        """Phases are executed in the order they are defined."""
        phases = [
            PhaseDefinition(name="phase1"),
            PhaseDefinition(name="phase2"),
            PhaseDefinition(name="phase3"),
        ]
        policy = make_policy(phases=phases)

        processor = WorkflowProcessor(
            conn=db_conn,
            policy=policy,
            dry_run=True,
        )

        executed_phases = []

        def mock_execute_phase(phase, file_path, file_info):
            executed_phases.append(phase.name)
            return make_phase_result(phase_name=phase.name)

        with (
            patch.object(
                processor, "_check_min_free_disk_threshold", return_value=None
            ),
            patch.object(processor, "_get_file_info", return_value=sample_file_info),
            patch.object(
                processor._executor, "execute_phase", side_effect=mock_execute_phase
            ),
        ):
            result = processor.process_file(test_file)

        assert result.success is True
        assert executed_phases == ["phase1", "phase2", "phase3"]
        assert result.phases_completed == 3

    def test_reintrospects_after_modification(
        self, db_conn, test_file, make_policy, make_phase_result, sample_file_info
    ):
        """File is re-introspected after a phase makes changes."""
        policy = make_policy(
            phases=[
                PhaseDefinition(name="modify"),
                PhaseDefinition(name="verify"),
            ]
        )

        processor = WorkflowProcessor(
            conn=db_conn,
            policy=policy,
            dry_run=False,  # Not dry-run so re-introspection happens
        )

        call_count = {"reintrospect": 0}

        def mock_reintrospect(file_path):
            call_count["reintrospect"] += 1
            return sample_file_info

        def mock_execute_phase(phase, file_path, file_info):
            # First phase makes changes
            changes = 1 if phase.name == "modify" else 0
            return make_phase_result(phase_name=phase.name, changes_made=changes)

        with (
            patch.object(
                processor, "_check_min_free_disk_threshold", return_value=None
            ),
            patch.object(processor, "_get_file_info", return_value=sample_file_info),
            patch.object(processor, "_re_introspect", side_effect=mock_reintrospect),
            patch.object(
                processor._executor, "execute_phase", side_effect=mock_execute_phase
            ),
        ):
            result = processor.process_file(test_file)

        assert result.success is True
        # Re-introspect should be called once after the modify phase
        assert call_count["reintrospect"] == 1

    def test_no_reintrospect_in_dry_run(
        self, db_conn, test_file, make_policy, make_phase_result, sample_file_info
    ):
        """No re-introspection in dry-run mode even when changes reported."""
        policy = make_policy(phases=[PhaseDefinition(name="modify")])

        processor = WorkflowProcessor(
            conn=db_conn,
            policy=policy,
            dry_run=True,  # Dry-run mode
        )

        reintrospect_called = {"called": False}

        def mock_reintrospect(file_path):
            reintrospect_called["called"] = True
            return sample_file_info

        def mock_execute_phase(phase, file_path, file_info):
            return make_phase_result(phase_name=phase.name, changes_made=5)

        with (
            patch.object(
                processor, "_check_min_free_disk_threshold", return_value=None
            ),
            patch.object(processor, "_get_file_info", return_value=sample_file_info),
            patch.object(processor, "_re_introspect", side_effect=mock_reintrospect),
            patch.object(
                processor._executor, "execute_phase", side_effect=mock_execute_phase
            ),
        ):
            processor.process_file(test_file)

        assert reintrospect_called["called"] is False


# =============================================================================
# Tests for on_error modes
# =============================================================================


class TestOnErrorModes:
    """Tests for error handling based on on_error configuration."""

    def test_respects_on_error_skip_mode(
        self, db_conn, test_file, make_policy, make_phase_result, sample_file_info
    ):
        """on_error=skip stops processing remaining phases for this file."""
        policy = make_policy(
            phases=[
                PhaseDefinition(name="phase1"),
                PhaseDefinition(name="phase2"),
                PhaseDefinition(name="phase3"),
            ],
            on_error=OnErrorMode.SKIP,
        )

        processor = WorkflowProcessor(
            conn=db_conn,
            policy=policy,
            dry_run=True,
        )

        def mock_execute_phase(phase, file_path, file_info):
            if phase.name == "phase1":
                raise PhaseExecutionError(
                    phase_name="phase1",
                    operation=None,
                    message="Test error",
                )
            return make_phase_result(phase_name=phase.name)

        with (
            patch.object(
                processor, "_check_min_free_disk_threshold", return_value=None
            ),
            patch.object(processor, "_get_file_info", return_value=sample_file_info),
            patch.object(
                processor._executor, "execute_phase", side_effect=mock_execute_phase
            ),
        ):
            result = processor.process_file(test_file)

        # Phase 1 failed, phases 2 & 3 were skipped
        assert result.phases_failed == 1
        assert result.phases_skipped == 2
        assert result.phases_completed == 0

    def test_respects_on_error_continue_mode(
        self, db_conn, test_file, make_policy, make_phase_result, sample_file_info
    ):
        """on_error=continue proceeds to next phase after error."""
        policy = make_policy(
            phases=[
                PhaseDefinition(name="phase1"),
                PhaseDefinition(name="phase2"),
                PhaseDefinition(name="phase3"),
            ],
            on_error=OnErrorMode.CONTINUE,
        )

        processor = WorkflowProcessor(
            conn=db_conn,
            policy=policy,
            dry_run=True,
        )

        def mock_execute_phase(phase, file_path, file_info):
            if phase.name == "phase2":
                raise PhaseExecutionError(
                    phase_name="phase2",
                    operation=None,
                    message="Test error",
                )
            return make_phase_result(phase_name=phase.name)

        with (
            patch.object(
                processor, "_check_min_free_disk_threshold", return_value=None
            ),
            patch.object(processor, "_get_file_info", return_value=sample_file_info),
            patch.object(
                processor._executor, "execute_phase", side_effect=mock_execute_phase
            ),
        ):
            result = processor.process_file(test_file)

        # Phase 2 failed but processing continued to phase 3
        assert result.phases_failed == 1
        assert result.phases_completed == 2  # phase1 and phase3

    def test_respects_on_error_fail_mode(
        self, db_conn, test_file, make_policy, make_phase_result, sample_file_info
    ):
        """on_error=fail stops batch processing."""
        policy = make_policy(
            phases=[
                PhaseDefinition(name="phase1"),
                PhaseDefinition(name="phase2"),
            ],
            on_error=OnErrorMode.FAIL,
        )

        processor = WorkflowProcessor(
            conn=db_conn,
            policy=policy,
            dry_run=True,
        )

        def mock_execute_phase(phase, file_path, file_info):
            if phase.name == "phase1":
                raise PhaseExecutionError(
                    phase_name="phase1",
                    operation=None,
                    message="Batch should stop",
                )
            return make_phase_result(phase_name=phase.name)

        with (
            patch.object(
                processor, "_check_min_free_disk_threshold", return_value=None
            ),
            patch.object(processor, "_get_file_info", return_value=sample_file_info),
            patch.object(
                processor._executor, "execute_phase", side_effect=mock_execute_phase
            ),
        ):
            result = processor.process_file(test_file)

        assert result.success is False
        assert result.failed_phase == "phase1"
        assert result.phases_skipped == 1  # phase2 was skipped

    def test_uses_phase_level_on_error_override(
        self, db_conn, test_file, make_policy, make_phase_result, sample_file_info
    ):
        """Per-phase on_error override takes precedence over global."""
        # Global is SKIP, but phase1 overrides to CONTINUE
        phases = [
            PhaseDefinition(name="phase1", on_error=OnErrorMode.CONTINUE),
            PhaseDefinition(name="phase2"),
            PhaseDefinition(name="phase3"),
        ]
        policy = make_policy(phases=phases, on_error=OnErrorMode.SKIP)

        processor = WorkflowProcessor(
            conn=db_conn,
            policy=policy,
            dry_run=True,
        )

        def mock_execute_phase(phase, file_path, file_info):
            if phase.name == "phase1":
                raise PhaseExecutionError(
                    phase_name="phase1",
                    operation=None,
                    message="Error",
                )
            return make_phase_result(phase_name=phase.name)

        with (
            patch.object(
                processor, "_check_min_free_disk_threshold", return_value=None
            ),
            patch.object(processor, "_get_file_info", return_value=sample_file_info),
            patch.object(
                processor._executor, "execute_phase", side_effect=mock_execute_phase
            ),
        ):
            result = processor.process_file(test_file)

        # Phase1 failed but CONTINUE was used (per-phase), so phase2 and phase3 ran
        assert result.phases_failed == 1
        assert result.phases_completed == 2


# =============================================================================
# Tests for skip conditions
# =============================================================================


class TestSkipConditions:
    """Tests for phase skip condition evaluation."""

    def test_check_dependency_condition_skips_when_dependency_failed(
        self, db_conn, test_file, make_policy, make_phase_result, sample_file_info
    ):
        """Phase is skipped when its dependency failed."""
        phases = [
            PhaseDefinition(name="phase1"),
            PhaseDefinition(name="phase2", depends_on=("phase1",)),
        ]
        policy = make_policy(phases=phases, on_error=OnErrorMode.CONTINUE)

        processor = WorkflowProcessor(
            conn=db_conn,
            policy=policy,
            dry_run=True,
        )

        def mock_execute_phase(phase, file_path, file_info):
            if phase.name == "phase1":
                raise PhaseExecutionError(
                    phase_name="phase1",
                    operation=None,
                    message="Error",
                )
            return make_phase_result(phase_name=phase.name)

        with (
            patch.object(
                processor, "_check_min_free_disk_threshold", return_value=None
            ),
            patch.object(processor, "_get_file_info", return_value=sample_file_info),
            patch.object(
                processor._executor, "execute_phase", side_effect=mock_execute_phase
            ),
        ):
            result = processor.process_file(test_file)

        # Phase1 failed, phase2 was skipped (dependency)
        assert result.phases_failed == 1
        assert result.phases_skipped == 1
        # Check the skip reason in phase results
        phase2_result = next(
            (r for r in result.phase_results if r.phase_name == "phase2"), None
        )
        assert phase2_result is not None
        assert phase2_result.outcome == PhaseOutcome.SKIPPED
        assert "dependency" in phase2_result.message.lower()

    def test_check_dependency_condition_passes_when_completed(
        self, db_conn, test_file, make_policy, make_phase_result, sample_file_info
    ):
        """Phase runs when its dependency completed successfully."""
        phases = [
            PhaseDefinition(name="phase1"),
            PhaseDefinition(name="phase2", depends_on=("phase1",)),
        ]
        policy = make_policy(phases=phases)

        processor = WorkflowProcessor(
            conn=db_conn,
            policy=policy,
            dry_run=True,
        )

        def mock_execute_phase(phase, file_path, file_info):
            return make_phase_result(phase_name=phase.name)

        with (
            patch.object(
                processor, "_check_min_free_disk_threshold", return_value=None
            ),
            patch.object(processor, "_get_file_info", return_value=sample_file_info),
            patch.object(
                processor._executor, "execute_phase", side_effect=mock_execute_phase
            ),
        ):
            result = processor.process_file(test_file)

        assert result.phases_completed == 2
        assert result.phases_skipped == 0

    def test_check_skip_condition_evaluates_skip_when(
        self, db_conn, test_file, make_policy, make_phase_result
    ):
        """Phase is skipped when skip_when condition matches."""
        # Create file info with HEVC codec
        file_info = FileInfo(
            path=test_file,
            filename=test_file.name,
            directory=test_file.parent,
            extension=".mkv",
            size_bytes=1000,
            modified_at=datetime.now(timezone.utc),
            container_format="matroska",
            tracks=(TrackInfo(index=0, track_type="video", codec="hevc"),),
        )

        # Phase skips when video codec is HEVC
        phases = [
            PhaseDefinition(
                name="transcode",
                skip_when=PhaseSkipCondition(video_codec=("hevc", "h265")),
            ),
        ]
        policy = make_policy(phases=phases)

        processor = WorkflowProcessor(
            conn=db_conn,
            policy=policy,
            dry_run=True,
        )

        with (
            patch.object(
                processor, "_check_min_free_disk_threshold", return_value=None
            ),
            patch.object(processor, "_get_file_info", return_value=file_info),
            patch.object(processor._executor, "execute_phase") as mock_execute,
        ):
            result = processor.process_file(test_file)

        # Phase should be skipped, execute_phase should not be called
        mock_execute.assert_not_called()
        assert result.phases_skipped == 1
        assert result.phases_completed == 0

    def test_check_run_if_condition_requires_phase_modified(
        self, db_conn, test_file, make_policy, make_phase_result, sample_file_info
    ):
        """Phase is skipped when run_if.phase_modified condition not met."""
        phases = [
            PhaseDefinition(name="transcode"),
            PhaseDefinition(
                name="verify",
                run_if=RunIfCondition(phase_modified="transcode"),
            ),
        ]
        policy = make_policy(phases=phases)

        processor = WorkflowProcessor(
            conn=db_conn,
            policy=policy,
            dry_run=True,
        )

        def mock_execute_phase(phase, file_path, file_info):
            # Transcode phase makes no changes
            return make_phase_result(phase_name=phase.name, changes_made=0)

        with (
            patch.object(
                processor, "_check_min_free_disk_threshold", return_value=None
            ),
            patch.object(processor, "_get_file_info", return_value=sample_file_info),
            patch.object(
                processor._executor, "execute_phase", side_effect=mock_execute_phase
            ),
        ):
            result = processor.process_file(test_file)

        # Transcode completed, verify was skipped (no modifications)
        assert result.phases_completed == 1
        assert result.phases_skipped == 1

    def test_run_if_phase_modified_passes_when_modified(
        self, db_conn, test_file, make_policy, make_phase_result, sample_file_info
    ):
        """Phase runs when run_if.phase_modified condition is met."""
        phases = [
            PhaseDefinition(name="transcode"),
            PhaseDefinition(
                name="verify",
                run_if=RunIfCondition(phase_modified="transcode"),
            ),
        ]
        policy = make_policy(phases=phases)

        processor = WorkflowProcessor(
            conn=db_conn,
            policy=policy,
            dry_run=True,
        )

        def mock_execute_phase(phase, file_path, file_info):
            # Transcode phase makes changes
            changes = 1 if phase.name == "transcode" else 0
            return make_phase_result(phase_name=phase.name, changes_made=changes)

        with (
            patch.object(
                processor, "_check_min_free_disk_threshold", return_value=None
            ),
            patch.object(processor, "_get_file_info", return_value=sample_file_info),
            patch.object(
                processor._executor, "execute_phase", side_effect=mock_execute_phase
            ),
        ):
            result = processor.process_file(test_file)

        # Both phases should complete
        assert result.phases_completed == 2
        assert result.phases_skipped == 0

    def test_skip_condition_priority_order(
        self, db_conn, test_file, make_policy, make_phase_result, sample_file_info
    ):
        """Dependency condition is checked before skip_when."""
        # Phase2 depends on phase1 and has skip_when
        # Dependency check should happen first
        phases = [
            PhaseDefinition(name="phase1"),
            PhaseDefinition(
                name="phase2",
                depends_on=("phase1",),
                skip_when=PhaseSkipCondition(video_codec=("h264",)),
            ),
        ]
        policy = make_policy(phases=phases, on_error=OnErrorMode.CONTINUE)

        processor = WorkflowProcessor(
            conn=db_conn,
            policy=policy,
            dry_run=True,
        )

        def mock_execute_phase(phase, file_path, file_info):
            if phase.name == "phase1":
                raise PhaseExecutionError(
                    phase_name="phase1",
                    operation=None,
                    message="Error",
                )
            return make_phase_result(phase_name=phase.name)

        with (
            patch.object(
                processor, "_check_min_free_disk_threshold", return_value=None
            ),
            patch.object(processor, "_get_file_info", return_value=sample_file_info),
            patch.object(
                processor._executor, "execute_phase", side_effect=mock_execute_phase
            ),
        ):
            result = processor.process_file(test_file)

        # Phase2 should be skipped due to dependency (not skip_when)
        phase2_result = next(
            (r for r in result.phase_results if r.phase_name == "phase2"), None
        )
        assert phase2_result is not None
        assert "dependency" in phase2_result.message.lower()


# =============================================================================
# Tests for re-introspection
# =============================================================================


class TestReIntrospection:
    """Tests for file re-introspection after modification."""

    def test_re_introspect_updates_database(
        self, db_conn, test_file, make_policy, make_phase_result, sample_file_info
    ):
        """Re-introspection updates tracks in database."""
        policy = make_policy(phases=[PhaseDefinition(name="modify")])

        processor = WorkflowProcessor(
            conn=db_conn,
            policy=policy,
            dry_run=False,
        )

        updated_file_info = FileInfo(
            path=test_file,
            filename=test_file.name,
            directory=test_file.parent,
            extension=".mkv",
            size_bytes=2000,  # Changed
            modified_at=datetime.now(timezone.utc),
            container_format="matroska",
            tracks=(
                TrackInfo(index=0, track_type="video", codec="hevc"),  # Changed
            ),
        )

        reintrospect_called = {"called": False}

        def mock_reintrospect(file_path):
            reintrospect_called["called"] = True
            return updated_file_info

        def mock_execute_phase(phase, file_path, file_info):
            return make_phase_result(phase_name=phase.name, changes_made=1)

        with (
            patch.object(
                processor, "_check_min_free_disk_threshold", return_value=None
            ),
            patch.object(processor, "_get_file_info", return_value=sample_file_info),
            patch.object(processor, "_re_introspect", side_effect=mock_reintrospect),
            patch.object(
                processor._executor, "execute_phase", side_effect=mock_execute_phase
            ),
        ):
            processor.process_file(test_file)

        assert reintrospect_called["called"] is True

    def test_re_introspect_raises_on_introspection_failure(
        self, db_conn, test_file, make_policy, make_phase_result, sample_file_info
    ):
        """PhaseExecutionError raised when re-introspection fails."""

        policy = make_policy(phases=[PhaseDefinition(name="modify")])

        processor = WorkflowProcessor(
            conn=db_conn,
            policy=policy,
            dry_run=False,
        )

        def mock_execute_phase(phase, file_path, file_info):
            return make_phase_result(phase_name=phase.name, changes_made=1)

        # Mock the actual _re_introspect to raise an error
        def mock_reintrospect_fails(file_path):
            raise PhaseExecutionError(
                phase_name="re-introspection",
                operation=None,
                message="Cannot re-introspect file after modification",
            )

        with (
            patch.object(
                processor, "_check_min_free_disk_threshold", return_value=None
            ),
            patch.object(processor, "_get_file_info", return_value=sample_file_info),
            patch.object(
                processor, "_re_introspect", side_effect=mock_reintrospect_fails
            ),
            patch.object(
                processor._executor, "execute_phase", side_effect=mock_execute_phase
            ),
        ):
            result = processor.process_file(test_file)

        # Should catch the error
        assert result.success is False
        assert "re-introspect" in result.error_message.lower()


# =============================================================================
# Tests for effective on_error resolution
# =============================================================================


class TestGetEffectiveOnError:
    """Tests for _get_effective_on_error method."""

    def test_uses_global_config_when_no_phase_override(self, db_conn, make_policy):
        """Uses global on_error when phase doesn't specify one."""
        policy = make_policy(
            phases=[PhaseDefinition(name="test")],
            on_error=OnErrorMode.FAIL,
        )
        processor = WorkflowProcessor(conn=db_conn, policy=policy)

        phase = PhaseDefinition(name="test", on_error=None)
        effective = processor._get_effective_on_error(phase)

        assert effective == OnErrorMode.FAIL

    def test_uses_phase_override_when_specified(self, db_conn, make_policy):
        """Uses phase-level on_error when specified."""
        policy = make_policy(
            phases=[PhaseDefinition(name="test", on_error=OnErrorMode.SKIP)],
            on_error=OnErrorMode.FAIL,
        )
        processor = WorkflowProcessor(conn=db_conn, policy=policy)

        phase = PhaseDefinition(name="test", on_error=OnErrorMode.SKIP)
        effective = processor._get_effective_on_error(phase)

        assert effective == OnErrorMode.SKIP


# =============================================================================
# Tests for selected phases
# =============================================================================


class TestSelectedPhases:
    """Tests for processing with selected phases."""

    def test_only_selected_phases_execute(
        self, db_conn, test_file, make_policy, make_phase_result, sample_file_info
    ):
        """Only selected phases are executed."""
        phases = [
            PhaseDefinition(name="phase1"),
            PhaseDefinition(name="phase2"),
            PhaseDefinition(name="phase3"),
        ]
        policy = make_policy(phases=phases)

        processor = WorkflowProcessor(
            conn=db_conn,
            policy=policy,
            dry_run=True,
            selected_phases=["phase1", "phase3"],  # Skip phase2
        )

        executed_phases = []

        def mock_execute_phase(phase, file_path, file_info):
            executed_phases.append(phase.name)
            return make_phase_result(phase_name=phase.name)

        with (
            patch.object(
                processor, "_check_min_free_disk_threshold", return_value=None
            ),
            patch.object(processor, "_get_file_info", return_value=sample_file_info),
            patch.object(
                processor._executor, "execute_phase", side_effect=mock_execute_phase
            ),
        ):
            result = processor.process_file(test_file)

        assert executed_phases == ["phase1", "phase3"]
        assert result.phases_completed == 2

    def test_raises_for_unknown_selected_phase(self, db_conn, make_policy):
        """ValueError raised for unknown phase name."""
        policy = make_policy(phases=[PhaseDefinition(name="phase1")])

        with pytest.raises(ValueError) as exc_info:
            WorkflowProcessor(
                conn=db_conn,
                policy=policy,
                selected_phases=["nonexistent"],
            )

        assert "Unknown phase 'nonexistent'" in str(exc_info.value)
