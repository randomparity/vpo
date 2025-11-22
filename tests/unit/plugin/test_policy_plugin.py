"""Unit tests for PolicyEnginePlugin."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from video_policy_orchestrator.db.models import TrackInfo
from video_policy_orchestrator.executor.interface import ExecutorResult
from video_policy_orchestrator.plugin.events import (
    PLAN_AFTER_EXECUTE,
    PLAN_BEFORE_EXECUTE,
    PLAN_EXECUTION_FAILED,
    POLICY_AFTER_EVALUATE,
    POLICY_BEFORE_EVALUATE,
    PlanExecuteEvent,
    PolicyEvaluateEvent,
)
from video_policy_orchestrator.plugin.interfaces import AnalyzerPlugin, MutatorPlugin
from video_policy_orchestrator.plugin.manifest import PluginSource
from video_policy_orchestrator.plugins.policy_engine.plugin import PolicyEnginePlugin
from video_policy_orchestrator.policy.models import (
    ActionType,
    Plan,
    PlannedAction,
    PolicySchema,
)


@pytest.fixture
def plugin() -> PolicyEnginePlugin:
    """Create a fresh PolicyEnginePlugin instance."""
    return PolicyEnginePlugin()


@pytest.fixture
def sample_policy() -> PolicySchema:
    """Create a sample policy for testing."""
    return PolicySchema(schema_version=1)


@pytest.fixture
def sample_tracks() -> list[TrackInfo]:
    """Create sample tracks for testing."""
    return [
        TrackInfo(index=0, track_type="video", codec="h264"),
        TrackInfo(index=1, track_type="audio", codec="aac", language="eng"),
        TrackInfo(index=2, track_type="audio", codec="ac3", language="jpn"),
        TrackInfo(index=3, track_type="subtitle", codec="subrip", language="eng"),
    ]


@pytest.fixture
def sample_plan(tmp_path: Path) -> Plan:
    """Create a sample execution plan."""
    return Plan(
        file_id="test-uuid",
        file_path=tmp_path / "test.mkv",
        policy_version=1,
        actions=(
            PlannedAction(
                action_type=ActionType.SET_DEFAULT,
                track_index=1,
                current_value=False,
                desired_value=True,
            ),
        ),
        requires_remux=False,
    )


@pytest.fixture
def empty_plan(tmp_path: Path) -> Plan:
    """Create an empty execution plan."""
    return Plan(
        file_id="test-uuid",
        file_path=tmp_path / "test.mkv",
        policy_version=1,
        actions=(),
        requires_remux=False,
    )


class TestPolicyEnginePluginMetadata:
    """Tests for plugin metadata and attributes."""

    def test_plugin_name(self, plugin: PolicyEnginePlugin):
        """Plugin has correct name."""
        assert plugin.name == "policy-engine"

    def test_plugin_version(self, plugin: PolicyEnginePlugin):
        """Plugin has correct version."""
        assert plugin.version == "1.0.0"

    def test_plugin_description(self, plugin: PolicyEnginePlugin):
        """Plugin has description."""
        assert plugin.description is not None
        assert len(plugin.description) > 0

    def test_plugin_api_versions(self, plugin: PolicyEnginePlugin):
        """Plugin declares API version compatibility."""
        assert plugin.min_api_version == "1.0.0"
        assert plugin.max_api_version == "1.99.99"

    def test_plugin_events(self, plugin: PolicyEnginePlugin):
        """Plugin subscribes to expected events."""
        assert POLICY_BEFORE_EVALUATE in plugin.events
        assert POLICY_AFTER_EVALUATE in plugin.events
        assert PLAN_BEFORE_EXECUTE in plugin.events
        assert PLAN_AFTER_EXECUTE in plugin.events
        assert PLAN_EXECUTION_FAILED in plugin.events

    def test_plugin_source(self, plugin: PolicyEnginePlugin):
        """Plugin is marked as built-in."""
        assert plugin.source == PluginSource.BUILTIN


class TestPolicyEnginePluginProtocols:
    """Tests for protocol compliance."""

    def test_implements_analyzer_protocol(self, plugin: PolicyEnginePlugin):
        """Plugin implements AnalyzerPlugin protocol."""
        assert isinstance(plugin, AnalyzerPlugin)

    def test_implements_mutator_protocol(self, plugin: PolicyEnginePlugin):
        """Plugin implements MutatorPlugin protocol."""
        assert isinstance(plugin, MutatorPlugin)

    def test_has_required_analyzer_methods(self, plugin: PolicyEnginePlugin):
        """Plugin has all required AnalyzerPlugin methods."""
        assert hasattr(plugin, "on_file_scanned")
        assert hasattr(plugin, "on_policy_evaluate")
        assert hasattr(plugin, "on_plan_complete")
        assert callable(plugin.on_file_scanned)
        assert callable(plugin.on_policy_evaluate)
        assert callable(plugin.on_plan_complete)

    def test_has_required_mutator_methods(self, plugin: PolicyEnginePlugin):
        """Plugin has all required MutatorPlugin methods."""
        assert hasattr(plugin, "on_plan_execute")
        assert hasattr(plugin, "execute")
        assert hasattr(plugin, "rollback")
        assert callable(plugin.on_plan_execute)
        assert callable(plugin.execute)
        assert callable(plugin.rollback)


class TestPolicyEnginePluginAnalyzerMethods:
    """Tests for AnalyzerPlugin method implementations."""

    def test_on_file_scanned_returns_none(self, plugin: PolicyEnginePlugin):
        """on_file_scanned returns None (no enrichment)."""
        mock_event = MagicMock()
        result = plugin.on_file_scanned(mock_event)
        assert result is None

    def test_on_policy_evaluate_before(
        self, plugin: PolicyEnginePlugin, tmp_path: Path
    ):
        """on_policy_evaluate handles before_evaluate event."""
        event = PolicyEvaluateEvent(
            file_path=tmp_path / "test.mkv",
            file_info=MagicMock(),
            policy=MagicMock(),
            plan=None,  # before_evaluate
        )
        # Should not raise
        plugin.on_policy_evaluate(event)

    def test_on_policy_evaluate_after(
        self, plugin: PolicyEnginePlugin, sample_plan: Plan, tmp_path: Path
    ):
        """on_policy_evaluate handles after_evaluate event."""
        event = PolicyEvaluateEvent(
            file_path=tmp_path / "test.mkv",
            file_info=MagicMock(),
            policy=MagicMock(),
            plan=sample_plan,  # after_evaluate
        )
        # Should not raise
        plugin.on_policy_evaluate(event)

    def test_on_plan_complete_success(
        self, plugin: PolicyEnginePlugin, sample_plan: Plan
    ):
        """on_plan_complete handles successful execution."""
        event = PlanExecuteEvent(
            plan=sample_plan,
            result=ExecutorResult(success=True, message="Done"),
            error=None,
        )
        # Should not raise
        plugin.on_plan_complete(event)

    def test_on_plan_complete_failure(
        self, plugin: PolicyEnginePlugin, sample_plan: Plan
    ):
        """on_plan_complete handles failed execution."""
        event = PlanExecuteEvent(
            plan=sample_plan,
            result=None,
            error=RuntimeError("Test error"),
        )
        # Should not raise
        plugin.on_plan_complete(event)


class TestPolicyEnginePluginMutatorMethods:
    """Tests for MutatorPlugin method implementations."""

    def test_on_plan_execute_returns_none(
        self, plugin: PolicyEnginePlugin, sample_plan: Plan
    ):
        """on_plan_execute returns None (no plan modification)."""
        event = PlanExecuteEvent(plan=sample_plan)
        result = plugin.on_plan_execute(event)
        assert result is None

    def test_execute_empty_plan(self, plugin: PolicyEnginePlugin, empty_plan: Plan):
        """execute returns success for empty plan."""
        result = plugin.execute(empty_plan)
        assert result.success is True
        assert "No changes" in result.message

    @patch(
        "video_policy_orchestrator.plugins.policy_engine.plugin.check_tool_availability"
    )
    @patch("video_policy_orchestrator.plugins.policy_engine.plugin.MkvpropeditExecutor")
    def test_execute_mkv_metadata_uses_mkvpropedit(
        self,
        mock_executor_class: MagicMock,
        mock_tools: MagicMock,
        plugin: PolicyEnginePlugin,
        sample_plan: Plan,
    ):
        """execute uses mkvpropedit for MKV metadata changes."""
        mock_tools.return_value = {"mkvpropedit": True, "mkvmerge": True}
        mock_executor = MagicMock()
        mock_executor.execute.return_value = ExecutorResult(success=True, message="OK")
        mock_executor_class.return_value = mock_executor

        result = plugin.execute(sample_plan)

        assert result.success is True
        mock_executor_class.assert_called_once()
        mock_executor.execute.assert_called_once()

    @patch(
        "video_policy_orchestrator.plugins.policy_engine.plugin.check_tool_availability"
    )
    def test_execute_missing_tool_returns_error(
        self,
        mock_tools: MagicMock,
        plugin: PolicyEnginePlugin,
        sample_plan: Plan,
    ):
        """execute returns error when required tool is missing."""
        mock_tools.return_value = {"mkvpropedit": False, "mkvmerge": False}

        result = plugin.execute(sample_plan)

        assert result.success is False
        assert (
            "mkvpropedit" in result.message.lower()
            or "mkvtoolnix" in result.message.lower()
        )

    def test_rollback_not_supported(
        self, plugin: PolicyEnginePlugin, sample_plan: Plan
    ):
        """rollback returns failure (not supported)."""
        result = plugin.rollback(sample_plan)
        assert result.success is False
        assert "not support" in result.message.lower()


class TestPolicyEnginePluginEvaluation:
    """Tests for policy evaluation method."""

    def test_evaluate_returns_plan(
        self,
        plugin: PolicyEnginePlugin,
        sample_policy: PolicySchema,
        sample_tracks: list[TrackInfo],
        tmp_path: Path,
    ):
        """evaluate returns a Plan object."""
        file_path = tmp_path / "test.mkv"

        plan = plugin.evaluate(
            file_id="test-uuid",
            file_path=file_path,
            container="mkv",
            tracks=sample_tracks,
            policy=sample_policy,
        )

        assert isinstance(plan, Plan)
        assert plan.file_id == "test-uuid"
        assert plan.file_path == file_path
        assert plan.policy_version == 1

    def test_evaluate_computes_actions(
        self,
        plugin: PolicyEnginePlugin,
        sample_policy: PolicySchema,
        sample_tracks: list[TrackInfo],
        tmp_path: Path,
    ):
        """evaluate produces actions based on policy."""
        # Create tracks that need default flag changes
        tracks = [
            TrackInfo(index=0, track_type="video", codec="h264", is_default=False),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="eng",
                is_default=False,
            ),
        ]

        plan = plugin.evaluate(
            file_id="test-uuid",
            file_path=tmp_path / "test.mkv",
            container="mkv",
            tracks=tracks,
            policy=sample_policy,
        )

        # Should have actions to set defaults
        assert len(plan.actions) > 0


class TestPolicyEnginePluginModule:
    """Tests for module-level exports."""

    def test_plugin_instance_exported(self):
        """Module exports plugin instance."""
        from video_policy_orchestrator.plugins.policy_engine import plugin

        assert isinstance(plugin, PolicyEnginePlugin)

    def test_plugin_class_exported(self):
        """Module exports PolicyEnginePlugin class."""
        from video_policy_orchestrator.plugins.policy_engine import PolicyEnginePlugin

        assert PolicyEnginePlugin is not None
