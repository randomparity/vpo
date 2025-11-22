"""Contract tests for plugin interfaces.

These tests verify that the plugin protocols work correctly and that
implementations can be validated at runtime.
"""

from pathlib import Path

from video_policy_orchestrator.plugin import (
    AnalyzerPlugin,
    FileScannedEvent,
    MutatorPlugin,
    PlanExecuteEvent,
    PolicyEvaluateEvent,
)


class TestAnalyzerPluginContract:
    """Contract tests for AnalyzerPlugin protocol."""

    def test_minimal_analyzer_is_recognized(self):
        """A class with required attributes should be recognized as AnalyzerPlugin."""

        class MinimalAnalyzer:
            name = "minimal-analyzer"
            version = "1.0.0"
            events = ["file.scanned"]

            def on_file_scanned(self, event: FileScannedEvent):
                return None

            def on_policy_evaluate(self, event: PolicyEvaluateEvent):
                pass

            def on_plan_complete(self, event: PlanExecuteEvent):
                pass

        plugin = MinimalAnalyzer()
        assert isinstance(plugin, AnalyzerPlugin)

    def test_analyzer_with_missing_name_not_recognized(self):
        """A class missing 'name' should not be recognized."""

        class MissingName:
            version = "1.0.0"
            events = ["file.scanned"]

            def on_file_scanned(self, event):
                return None

            def on_policy_evaluate(self, event):
                pass

            def on_plan_complete(self, event):
                pass

        plugin = MissingName()
        assert not isinstance(plugin, AnalyzerPlugin)

    def test_analyzer_with_missing_events_not_recognized(self):
        """A class missing 'events' should not be recognized."""

        class MissingEvents:
            name = "missing-events"
            version = "1.0.0"

            def on_file_scanned(self, event):
                return None

            def on_policy_evaluate(self, event):
                pass

            def on_plan_complete(self, event):
                pass

        plugin = MissingEvents()
        assert not isinstance(plugin, AnalyzerPlugin)

    def test_analyzer_can_return_enrichment_dict(self):
        """Analyzer on_file_scanned can return enrichment data."""

        class EnrichingAnalyzer:
            name = "enriching-analyzer"
            version = "1.0.0"
            events = ["file.scanned"]

            def on_file_scanned(self, event: FileScannedEvent):
                return {"custom_field": "custom_value"}

            def on_policy_evaluate(self, event):
                pass

            def on_plan_complete(self, event):
                pass

        plugin = EnrichingAnalyzer()
        event = FileScannedEvent(
            file_path=Path("/test/file.mkv"),
            file_info=None,
            tracks=[],
        )
        result = plugin.on_file_scanned(event)
        assert result == {"custom_field": "custom_value"}


class TestMutatorPluginContract:
    """Contract tests for MutatorPlugin protocol."""

    def test_minimal_mutator_is_recognized(self):
        """A class with required attributes should be recognized as MutatorPlugin."""

        class MinimalMutator:
            name = "minimal-mutator"
            version = "1.0.0"
            events = ["plan.before_execute"]

            def on_plan_execute(self, event: PlanExecuteEvent):
                return None

            def execute(self, plan):
                return {"success": True}

            def rollback(self, plan):
                return {"success": True}

        plugin = MinimalMutator()
        assert isinstance(plugin, MutatorPlugin)

    def test_mutator_with_missing_name_not_recognized(self):
        """A class missing 'name' should not be recognized."""

        class MissingName:
            version = "1.0.0"
            events = ["plan.before_execute"]

            def on_plan_execute(self, event):
                return None

            def execute(self, plan):
                return {"success": True}

            def rollback(self, plan):
                return {"success": True}

        plugin = MissingName()
        assert not isinstance(plugin, MutatorPlugin)

    def test_mutator_can_modify_plan(self):
        """Mutator on_plan_execute can return modified plan."""

        class ModifyingMutator:
            name = "modifying-mutator"
            version = "1.0.0"
            events = ["plan.before_execute"]

            def on_plan_execute(self, event: PlanExecuteEvent):
                # Return a modified plan (in reality this would be a Plan object)
                return {"modified": True}

            def execute(self, plan):
                return {"success": True}

            def rollback(self, plan):
                return {"success": True}

        plugin = ModifyingMutator()
        event = PlanExecuteEvent(plan={"original": True})
        result = plugin.on_plan_execute(event)
        assert result == {"modified": True}


class TestDualPluginContract:
    """Contract tests for plugins implementing both protocols."""

    def test_dual_plugin_is_both_analyzer_and_mutator(self):
        """A plugin can implement both AnalyzerPlugin and MutatorPlugin."""

        class DualPlugin:
            name = "dual-plugin"
            version = "1.0.0"
            events = ["file.scanned", "plan.before_execute"]

            def on_file_scanned(self, event):
                return None

            def on_policy_evaluate(self, event):
                pass

            def on_plan_complete(self, event):
                pass

            def on_plan_execute(self, event):
                return None

            def execute(self, plan):
                return {"success": True}

            def rollback(self, plan):
                return {"success": True}

        plugin = DualPlugin()
        assert isinstance(plugin, AnalyzerPlugin)
        assert isinstance(plugin, MutatorPlugin)
