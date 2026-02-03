"""Unit tests for container metadata action execution."""

from __future__ import annotations

from pathlib import Path

from vpo.policy.actions import (
    ActionContext,
    _resolve_container_metadata_value,
    execute_set_container_metadata_action,
)
from vpo.policy.types import (
    PluginMetadataReference,
    SetContainerMetadataAction,
)


class TestResolveContainerMetadataValue:
    """Tests for _resolve_container_metadata_value function."""

    def test_static_value(self) -> None:
        """Returns static value directly."""
        action = SetContainerMetadataAction(
            field="title",
            value="My Movie",
        )
        context = ActionContext(file_path=Path("/test/video.mkv"), rule_name="test")

        result = _resolve_container_metadata_value(action, context)

        assert result == "My Movie"

    def test_dynamic_value_from_plugin_metadata(self) -> None:
        """Resolves value from plugin metadata reference."""
        action = SetContainerMetadataAction(
            field="title",
            value=None,
            from_plugin_metadata=PluginMetadataReference(
                plugin="radarr", field="title"
            ),
        )
        context = ActionContext(
            file_path=Path("/test/video.mkv"),
            rule_name="test",
            plugin_metadata={"radarr": {"title": "Movie Title"}},
        )

        result = _resolve_container_metadata_value(action, context)

        assert result == "Movie Title"

    def test_missing_plugin_metadata_returns_none(self) -> None:
        """Returns None when plugin_metadata is not in context."""
        action = SetContainerMetadataAction(
            field="title",
            value=None,
            from_plugin_metadata=PluginMetadataReference(
                plugin="radarr", field="title"
            ),
        )
        context = ActionContext(
            file_path=Path("/test/video.mkv"),
            rule_name="test",
            plugin_metadata=None,
        )

        result = _resolve_container_metadata_value(action, context)

        assert result is None

    def test_missing_plugin_name_returns_none(self) -> None:
        """Returns None when referenced plugin not in metadata dict."""
        action = SetContainerMetadataAction(
            field="title",
            value=None,
            from_plugin_metadata=PluginMetadataReference(
                plugin="sonarr", field="title"
            ),
        )
        context = ActionContext(
            file_path=Path("/test/video.mkv"),
            rule_name="test",
            plugin_metadata={"radarr": {"title": "Movie Title"}},
        )

        result = _resolve_container_metadata_value(action, context)

        assert result is None

    def test_missing_field_in_plugin_returns_none(self) -> None:
        """Returns None when field not found in plugin metadata."""
        action = SetContainerMetadataAction(
            field="title",
            value=None,
            from_plugin_metadata=PluginMetadataReference(
                plugin="radarr", field="missing_field"
            ),
        )
        context = ActionContext(
            file_path=Path("/test/video.mkv"),
            rule_name="test",
            plugin_metadata={"radarr": {"title": "Movie Title"}},
        )

        result = _resolve_container_metadata_value(action, context)

        assert result is None

    def test_static_string_value_returned(self) -> None:
        """Static string value is returned as-is."""
        action = SetContainerMetadataAction(
            field="year",
            value="2024",
        )
        context = ActionContext(file_path=Path("/test/video.mkv"), rule_name="test")

        result = _resolve_container_metadata_value(action, context)

        assert result == "2024"

    def test_plugin_resolved_value_sanitized(self) -> None:
        """Plugin-resolved values are sanitized."""
        action = SetContainerMetadataAction(
            field="title",
            value=None,
            from_plugin_metadata=PluginMetadataReference(
                plugin="radarr", field="title"
            ),
        )
        context = ActionContext(
            file_path=Path("/test/video.mkv"),
            rule_name="test",
            plugin_metadata={"radarr": {"title": "  Good Title  "}},
        )

        result = _resolve_container_metadata_value(action, context)

        assert result is not None
        assert "Good Title" in result

    def test_plugin_resolved_value_truncated_when_too_long(self) -> None:
        """Plugin-resolved values exceeding max length are truncated."""
        long_value = "x" * 5000
        action = SetContainerMetadataAction(
            field="title",
            value=None,
            from_plugin_metadata=PluginMetadataReference(
                plugin="radarr", field="title"
            ),
        )
        context = ActionContext(
            file_path=Path("/test/video.mkv"),
            rule_name="test",
            plugin_metadata={"radarr": {"title": long_value}},
        )

        result = _resolve_container_metadata_value(action, context)

        assert result is not None
        assert len(result) == 4096

    def test_plugin_resolved_none_field_value_returns_none(self) -> None:
        """Plugin-resolved value that is None returns None."""
        action = SetContainerMetadataAction(
            field="title",
            value=None,
            from_plugin_metadata=PluginMetadataReference(
                plugin="radarr", field="title"
            ),
        )
        context = ActionContext(
            file_path=Path("/test/video.mkv"),
            rule_name="test",
            plugin_metadata={"radarr": {"title": None}},
        )

        result = _resolve_container_metadata_value(action, context)

        assert result is None


class TestExecuteSetContainerMetadataAction:
    """Tests for execute_set_container_metadata_action function."""

    def test_adds_metadata_change_to_context(self) -> None:
        """Successfully adds a container metadata change."""
        action = SetContainerMetadataAction(
            field="title",
            value="New Title",
        )
        context = ActionContext(file_path=Path("/test/video.mkv"), rule_name="test")

        result = execute_set_container_metadata_action(action, context)

        assert len(result.container_metadata_changes) == 1
        change = result.container_metadata_changes[0]
        assert change.field == "title"
        assert change.new_value == "New Title"

    def test_skips_when_value_unresolvable(self) -> None:
        """Skips action when value cannot be resolved."""
        action = SetContainerMetadataAction(
            field="title",
            value=None,
            from_plugin_metadata=PluginMetadataReference(
                plugin="missing", field="title"
            ),
        )
        context = ActionContext(
            file_path=Path("/test/video.mkv"),
            rule_name="test",
            plugin_metadata=None,
        )

        result = execute_set_container_metadata_action(action, context)

        assert len(result.container_metadata_changes) == 0
