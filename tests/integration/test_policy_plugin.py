"""Integration tests for PolicyEnginePlugin.

This module validates that the policy engine works correctly when accessed
through the plugin system, ensuring the refactoring to a plugin architecture
didn't break existing functionality.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.db.models import TrackInfo
from vpo.executor.interface import ExecutorResult
from vpo.plugin.events import (
    PLAN_AFTER_EXECUTE,
    PLAN_BEFORE_EXECUTE,
    POLICY_AFTER_EVALUATE,
    POLICY_BEFORE_EVALUATE,
    PlanExecuteEvent,
    PolicyEvaluateEvent,
)
from vpo.plugin.registry import PluginRegistry
from vpo.plugins.policy_engine import (
    PolicyEnginePlugin,
    plugin_instance,
)
from vpo.policy.models import (
    ActionType,
    DefaultFlagsConfig,
    PolicySchema,
    TrackType,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def registry() -> PluginRegistry:
    """Create a registry with the policy engine plugin registered."""
    reg = PluginRegistry()
    reg.load_builtin_plugins()
    return reg


@pytest.fixture
def default_policy() -> PolicySchema:
    """Create a default policy for testing."""
    return PolicySchema(
        schema_version=12,
        track_order=(
            TrackType.VIDEO,
            TrackType.AUDIO_MAIN,
            TrackType.AUDIO_ALTERNATE,
            TrackType.SUBTITLE_MAIN,
            TrackType.SUBTITLE_FORCED,
            TrackType.AUDIO_COMMENTARY,
            TrackType.SUBTITLE_COMMENTARY,
            TrackType.ATTACHMENT,
        ),
        audio_language_preference=("eng", "und"),
        subtitle_language_preference=("eng", "und"),
        commentary_patterns=("commentary", "director"),
        default_flags=DefaultFlagsConfig(
            set_first_video_default=True,
            set_preferred_audio_default=True,
            set_preferred_subtitle_default=False,
            clear_other_defaults=True,
        ),
    )


@pytest.fixture
def sample_tracks() -> list[TrackInfo]:
    """Create sample tracks for testing."""
    return [
        TrackInfo(index=0, track_type="video", codec="h264", is_default=False),
        TrackInfo(
            index=1, track_type="audio", codec="aac", language="eng", is_default=False
        ),
        TrackInfo(
            index=2, track_type="audio", codec="ac3", language="jpn", is_default=True
        ),
        TrackInfo(
            index=3,
            track_type="subtitle",
            codec="subrip",
            language="eng",
            is_default=False,
        ),
    ]


@pytest.fixture
def compliant_tracks() -> list[TrackInfo]:
    """Create tracks that are already policy-compliant."""
    return [
        TrackInfo(index=0, track_type="video", codec="h264", is_default=True),
        TrackInfo(
            index=1, track_type="audio", codec="aac", language="eng", is_default=True
        ),
        TrackInfo(
            index=2,
            track_type="subtitle",
            codec="subrip",
            language="eng",
            is_default=False,
        ),
    ]


# =============================================================================
# Plugin Discovery Integration Tests
# =============================================================================


class TestPolicyEnginePluginDiscovery:
    """Tests for policy engine plugin registration and discovery."""

    def test_policy_engine_is_registered(self, registry: PluginRegistry):
        """Policy engine should be registered as a built-in plugin."""
        loaded = registry.get("policy-engine")
        assert loaded is not None
        assert loaded.manifest.name == "policy-engine"

    def test_policy_engine_is_enabled_by_default(self, registry: PluginRegistry):
        """Policy engine should be enabled by default."""
        loaded = registry.get("policy-engine")
        assert loaded is not None
        assert loaded.enabled is True

    def test_policy_engine_subscribes_to_events(self, registry: PluginRegistry):
        """Policy engine should be subscribed to policy and plan events."""
        policy_plugins = registry.get_by_event(POLICY_BEFORE_EVALUATE)
        assert any(p.manifest.name == "policy-engine" for p in policy_plugins)

        plan_plugins = registry.get_by_event(PLAN_BEFORE_EXECUTE)
        assert any(p.manifest.name == "policy-engine" for p in plan_plugins)

    def test_module_exports_plugin_instance(self):
        """Plugin module should export a usable plugin instance."""
        assert plugin_instance is not None
        assert isinstance(plugin_instance, PolicyEnginePlugin)
        assert plugin_instance.name == "policy-engine"


# =============================================================================
# Policy Evaluation Integration Tests
# =============================================================================


class TestPolicyEngineEvaluationIntegration:
    """Tests for policy evaluation through the plugin."""

    def test_evaluate_produces_plan(
        self,
        registry: PluginRegistry,
        default_policy: PolicySchema,
        sample_tracks: list[TrackInfo],
        tmp_path: Path,
    ):
        """Plugin evaluation should produce a valid Plan."""
        loaded = registry.get("policy-engine")
        assert loaded is not None
        plugin_instance = loaded.instance

        file_path = tmp_path / "test.mkv"
        plan = plugin_instance.evaluate(
            file_id="test-uuid",
            file_path=file_path,
            container="mkv",
            tracks=sample_tracks,
            policy=default_policy,
        )

        assert plan is not None
        assert plan.file_id == "test-uuid"
        assert plan.file_path == file_path
        assert plan.policy_version == 12

    def test_evaluate_detects_default_flag_changes(
        self,
        registry: PluginRegistry,
        default_policy: PolicySchema,
        sample_tracks: list[TrackInfo],
        tmp_path: Path,
    ):
        """Plugin should detect tracks needing default flag changes."""
        loaded = registry.get("policy-engine")
        assert loaded is not None
        plugin_instance = loaded.instance

        plan = plugin_instance.evaluate(
            file_id="test-uuid",
            file_path=tmp_path / "test.mkv",
            container="mkv",
            tracks=sample_tracks,
            policy=default_policy,
        )

        # Should have actions for:
        # - Video needs SET_DEFAULT (is_default=False)
        # - English audio needs SET_DEFAULT (is_default=False)
        # - Japanese audio needs CLEAR_DEFAULT (is_default=True but not preferred)
        set_defaults = [
            a for a in plan.actions if a.action_type == ActionType.SET_DEFAULT
        ]
        clear_defaults = [
            a for a in plan.actions if a.action_type == ActionType.CLEAR_DEFAULT
        ]

        assert len(set_defaults) >= 2  # Video and English audio
        assert len(clear_defaults) >= 1  # Japanese audio

    def test_evaluate_compliant_file_empty_plan(
        self,
        registry: PluginRegistry,
        default_policy: PolicySchema,
        compliant_tracks: list[TrackInfo],
        tmp_path: Path,
    ):
        """Plugin should return empty plan for compliant files."""
        loaded = registry.get("policy-engine")
        assert loaded is not None
        plugin_instance = loaded.instance

        plan = plugin_instance.evaluate(
            file_id="test-uuid",
            file_path=tmp_path / "test.mkv",
            container="mkv",
            tracks=compliant_tracks,
            policy=default_policy,
        )

        assert plan.is_empty
        assert plan.summary == "No changes required"

    def test_evaluate_detects_track_reorder(
        self,
        registry: PluginRegistry,
        default_policy: PolicySchema,
        tmp_path: Path,
    ):
        """Plugin should detect when tracks need reordering."""
        loaded = registry.get("policy-engine")
        assert loaded is not None
        plugin_instance = loaded.instance

        # Tracks in wrong order (subtitle before video)
        out_of_order_tracks = [
            TrackInfo(
                index=0,
                track_type="subtitle",
                codec="subrip",
                language="eng",
                is_default=False,
            ),
            TrackInfo(index=1, track_type="video", codec="h264", is_default=True),
            TrackInfo(
                index=2,
                track_type="audio",
                codec="aac",
                language="eng",
                is_default=True,
            ),
        ]

        plan = plugin_instance.evaluate(
            file_id="test-uuid",
            file_path=tmp_path / "test.mkv",
            container="mkv",
            tracks=out_of_order_tracks,
            policy=default_policy,
        )

        assert plan.requires_remux
        reorder_actions = [
            a for a in plan.actions if a.action_type == ActionType.REORDER
        ]
        assert len(reorder_actions) == 1


# =============================================================================
# Plan Execution Integration Tests
# =============================================================================


class TestPolicyEngineExecutionIntegration:
    """Tests for plan execution through the plugin."""

    def test_execute_empty_plan_succeeds(
        self,
        registry: PluginRegistry,
        default_policy: PolicySchema,
        compliant_tracks: list[TrackInfo],
        tmp_path: Path,
    ):
        """Executing an empty plan should succeed."""
        loaded = registry.get("policy-engine")
        assert loaded is not None
        plugin_instance = loaded.instance

        # Generate empty plan from compliant file
        plan = plugin_instance.evaluate(
            file_id="test-uuid",
            file_path=tmp_path / "test.mkv",
            container="mkv",
            tracks=compliant_tracks,
            policy=default_policy,
        )

        result = plugin_instance.execute(plan)
        assert result.success is True
        assert "No changes" in result.message

    @patch("vpo.plugins.policy_engine.plugin.check_tool_availability")
    @patch("vpo.plugins.policy_engine.plugin.MkvpropeditExecutor")
    def test_execute_mkv_plan_uses_mkvpropedit(
        self,
        mock_executor_class: MagicMock,
        mock_tools: MagicMock,
        registry: PluginRegistry,
        default_policy: PolicySchema,
        sample_tracks: list[TrackInfo],
        tmp_path: Path,
    ):
        """Executing MKV metadata plan should use mkvpropedit."""
        mock_tools.return_value = {"mkvpropedit": True, "mkvmerge": True}
        mock_executor = MagicMock()
        mock_executor.execute.return_value = ExecutorResult(
            success=True, message="Changes applied"
        )
        mock_executor_class.return_value = mock_executor

        loaded = registry.get("policy-engine")
        assert loaded is not None
        plugin_instance = loaded.instance

        plan = plugin_instance.evaluate(
            file_id="test-uuid",
            file_path=tmp_path / "test.mkv",
            container="mkv",
            tracks=sample_tracks,
            policy=default_policy,
        )

        result = plugin_instance.execute(plan)

        assert result.success is True
        mock_executor_class.assert_called_once()
        mock_executor.execute.assert_called_once()

    @patch("vpo.plugins.policy_engine.plugin.check_tool_availability")
    def test_execute_missing_tool_fails_gracefully(
        self,
        mock_tools: MagicMock,
        registry: PluginRegistry,
        default_policy: PolicySchema,
        sample_tracks: list[TrackInfo],
        tmp_path: Path,
    ):
        """Executing without required tool should fail gracefully."""
        mock_tools.return_value = {"mkvpropedit": False, "mkvmerge": False}

        loaded = registry.get("policy-engine")
        assert loaded is not None
        plugin_instance = loaded.instance

        plan = plugin_instance.evaluate(
            file_id="test-uuid",
            file_path=tmp_path / "test.mkv",
            container="mkv",
            tracks=sample_tracks,
            policy=default_policy,
        )

        result = plugin_instance.execute(plan)

        assert result.success is False
        # Should mention mkvpropedit or mkvtoolnix
        assert (
            "mkvpropedit" in result.message.lower()
            or "mkvtoolnix" in result.message.lower()
        )


# =============================================================================
# Event Handler Integration Tests
# =============================================================================


class TestPolicyEngineEventIntegration:
    """Tests for plugin event handling through the registry."""

    def test_before_evaluate_event_handled(
        self,
        registry: PluginRegistry,
        default_policy: PolicySchema,
        tmp_path: Path,
    ):
        """Plugin should handle policy.before_evaluate event."""
        plugins = registry.get_by_event(POLICY_BEFORE_EVALUATE)
        policy_plugin = next(
            (p for p in plugins if p.manifest.name == "policy-engine"), None
        )
        assert policy_plugin is not None

        event = PolicyEvaluateEvent(
            file_path=tmp_path / "test.mkv",
            file_info=MagicMock(),
            policy=default_policy,
            plan=None,  # before_evaluate
        )

        # Should not raise
        policy_plugin.instance.on_policy_evaluate(event)

    def test_after_evaluate_event_handled(
        self,
        registry: PluginRegistry,
        default_policy: PolicySchema,
        sample_tracks: list[TrackInfo],
        tmp_path: Path,
    ):
        """Plugin should handle policy.after_evaluate event."""
        loaded = registry.get("policy-engine")
        assert loaded is not None
        plugin_instance = loaded.instance

        # Generate a plan
        plan = plugin_instance.evaluate(
            file_id="test-uuid",
            file_path=tmp_path / "test.mkv",
            container="mkv",
            tracks=sample_tracks,
            policy=default_policy,
        )

        plugins = registry.get_by_event(POLICY_AFTER_EVALUATE)
        policy_plugin = next(
            (p for p in plugins if p.manifest.name == "policy-engine"), None
        )
        assert policy_plugin is not None

        event = PolicyEvaluateEvent(
            file_path=tmp_path / "test.mkv",
            file_info=MagicMock(),
            policy=default_policy,
            plan=plan,  # after_evaluate
        )

        # Should not raise
        policy_plugin.instance.on_policy_evaluate(event)

    def test_before_execute_event_handled(
        self,
        registry: PluginRegistry,
        default_policy: PolicySchema,
        sample_tracks: list[TrackInfo],
        tmp_path: Path,
    ):
        """Plugin should handle plan.before_execute event."""
        loaded = registry.get("policy-engine")
        assert loaded is not None
        plugin_instance = loaded.instance

        plan = plugin_instance.evaluate(
            file_id="test-uuid",
            file_path=tmp_path / "test.mkv",
            container="mkv",
            tracks=sample_tracks,
            policy=default_policy,
        )

        plugins = registry.get_by_event(PLAN_BEFORE_EXECUTE)
        policy_plugin = next(
            (p for p in plugins if p.manifest.name == "policy-engine"), None
        )
        assert policy_plugin is not None

        event = PlanExecuteEvent(plan=plan)
        result = policy_plugin.instance.on_plan_execute(event)

        # Policy engine passes through unchanged
        assert result is None

    def test_after_execute_event_handled(
        self,
        registry: PluginRegistry,
        default_policy: PolicySchema,
        sample_tracks: list[TrackInfo],
        tmp_path: Path,
    ):
        """Plugin should handle plan.after_execute event."""
        loaded = registry.get("policy-engine")
        assert loaded is not None
        plugin_instance = loaded.instance

        plan = plugin_instance.evaluate(
            file_id="test-uuid",
            file_path=tmp_path / "test.mkv",
            container="mkv",
            tracks=sample_tracks,
            policy=default_policy,
        )

        plugins = registry.get_by_event(PLAN_AFTER_EXECUTE)
        policy_plugin = next(
            (p for p in plugins if p.manifest.name == "policy-engine"), None
        )
        assert policy_plugin is not None

        event = PlanExecuteEvent(
            plan=plan,
            result=ExecutorResult(success=True, message="Done"),
            error=None,
        )

        # Should not raise
        policy_plugin.instance.on_plan_complete(event)


# =============================================================================
# Compatibility Tests with Existing Policy Evaluator
# =============================================================================


class TestPolicyEngineBackwardsCompatibility:
    """Tests ensuring backwards compatibility with existing behavior."""

    def test_same_results_as_direct_evaluator(
        self,
        default_policy: PolicySchema,
        sample_tracks: list[TrackInfo],
        tmp_path: Path,
    ):
        """Plugin evaluate should produce same results as direct evaluator."""
        from vpo.policy.evaluator import evaluate_policy

        file_path = tmp_path / "test.mkv"

        # Direct evaluator
        direct_plan = evaluate_policy(
            file_id="test-uuid",
            file_path=file_path,
            container="mkv",
            tracks=sample_tracks,
            policy=default_policy,
        )

        # Plugin evaluator
        plugin_plan = plugin_instance.evaluate(
            file_id="test-uuid",
            file_path=file_path,
            container="mkv",
            tracks=sample_tracks,
            policy=default_policy,
        )

        # Results should be identical
        assert len(direct_plan.actions) == len(plugin_plan.actions)
        assert direct_plan.requires_remux == plugin_plan.requires_remux
        assert direct_plan.is_empty == plugin_plan.is_empty

        # Check each action type count matches
        for action_type in ActionType:
            direct_count = sum(
                1 for a in direct_plan.actions if a.action_type == action_type
            )
            plugin_count = sum(
                1 for a in plugin_plan.actions if a.action_type == action_type
            )
            assert direct_count == plugin_count, (
                f"Mismatch for {action_type}: "
                f"direct={direct_count}, plugin={plugin_count}"
            )

    def test_language_preference_handled_correctly(
        self,
        tmp_path: Path,
    ):
        """Plugin should respect language preference like direct evaluator."""
        japanese_policy = PolicySchema(
            schema_version=12,
            audio_language_preference=("jpn", "eng", "und"),
            subtitle_language_preference=("eng", "und"),
            default_flags=DefaultFlagsConfig(
                set_first_video_default=True,
                set_preferred_audio_default=True,
                set_preferred_subtitle_default=True,
                clear_other_defaults=True,
            ),
        )

        tracks = [
            TrackInfo(index=0, track_type="video", codec="h264", is_default=False),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="eng",
                is_default=True,
            ),
            TrackInfo(
                index=2,
                track_type="audio",
                codec="aac",
                language="jpn",
                is_default=False,
            ),
        ]

        plan = plugin_instance.evaluate(
            file_id="test-uuid",
            file_path=tmp_path / "test.mkv",
            container="mkv",
            tracks=tracks,
            policy=japanese_policy,
        )

        # Should clear English audio default and set Japanese
        clear_defaults = [
            a for a in plan.actions if a.action_type == ActionType.CLEAR_DEFAULT
        ]
        set_defaults = [
            a for a in plan.actions if a.action_type == ActionType.SET_DEFAULT
        ]

        assert any(a.track_index == 1 for a in clear_defaults)  # Clear English
        assert any(a.track_index == 2 for a in set_defaults)  # Set Japanese

    def test_commentary_detection_works(
        self,
        default_policy: PolicySchema,
        tmp_path: Path,
    ):
        """Plugin should detect commentary tracks correctly."""
        tracks = [
            TrackInfo(index=0, track_type="video", codec="h264", is_default=True),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="eng",
                title="Director Commentary",
                is_default=True,
            ),
            TrackInfo(
                index=2,
                track_type="audio",
                codec="aac",
                language="eng",
                is_default=False,
            ),
        ]

        plan = plugin_instance.evaluate(
            file_id="test-uuid",
            file_path=tmp_path / "test.mkv",
            container="mkv",
            tracks=tracks,
            policy=default_policy,
        )

        # Commentary track should have default cleared
        # Non-commentary English audio should be set as default
        clear_defaults = [
            a for a in plan.actions if a.action_type == ActionType.CLEAR_DEFAULT
        ]
        set_defaults = [
            a for a in plan.actions if a.action_type == ActionType.SET_DEFAULT
        ]

        assert any(a.track_index == 1 for a in clear_defaults)  # Clear commentary
        assert any(a.track_index == 2 for a in set_defaults)  # Set non-commentary
