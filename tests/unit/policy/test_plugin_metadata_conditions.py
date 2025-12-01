"""Unit tests for plugin metadata condition evaluation (V12)."""

from __future__ import annotations

import pytest

from video_policy_orchestrator.policy.conditions import (
    PluginMetadataDict,
    evaluate_plugin_metadata,
)
from video_policy_orchestrator.policy.models import (
    PluginMetadataCondition,
    PluginMetadataOperator,
)


class TestEvaluatePluginMetadata:
    """Tests for evaluate_plugin_metadata function."""

    def test_eq_string_match(self) -> None:
        """Test equality comparison with matching string."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="jpn",
            operator=PluginMetadataOperator.EQ,
        )
        metadata: PluginMetadataDict = {"radarr": {"original_language": "jpn"}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is True
        assert "True" in reason
        assert "actual='jpn'" in reason

    def test_eq_string_case_insensitive(self) -> None:
        """Test equality comparison is case-insensitive for strings."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="JPN",
            operator=PluginMetadataOperator.EQ,
        )
        metadata: PluginMetadataDict = {"radarr": {"original_language": "jpn"}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is True

    def test_eq_string_no_match(self) -> None:
        """Test equality comparison with non-matching string."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="eng",
            operator=PluginMetadataOperator.EQ,
        )
        metadata: PluginMetadataDict = {"radarr": {"original_language": "jpn"}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is False
        assert "False" in reason

    def test_eq_integer_match(self) -> None:
        """Test equality comparison with matching integer."""
        condition = PluginMetadataCondition(
            plugin="sonarr",
            field="season_count",
            value=12,
            operator=PluginMetadataOperator.EQ,
        )
        metadata: PluginMetadataDict = {"sonarr": {"season_count": 12}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is True

    def test_neq_string_match(self) -> None:
        """Test not-equal comparison with different string."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="eng",
            operator=PluginMetadataOperator.NEQ,
        )
        metadata: PluginMetadataDict = {"radarr": {"original_language": "jpn"}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is True

    def test_neq_string_same(self) -> None:
        """Test not-equal comparison with same string."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="jpn",
            operator=PluginMetadataOperator.NEQ,
        )
        metadata: PluginMetadataDict = {"radarr": {"original_language": "jpn"}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is False

    def test_contains_substring_match(self) -> None:
        """Test contains comparison with matching substring."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="title",
            value="anime",
            operator=PluginMetadataOperator.CONTAINS,
        )
        metadata: PluginMetadataDict = {"radarr": {"title": "My Favorite Anime Movie"}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is True

    def test_contains_case_insensitive(self) -> None:
        """Test contains comparison is case-insensitive."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="title",
            value="ANIME",
            operator=PluginMetadataOperator.CONTAINS,
        )
        metadata: PluginMetadataDict = {"radarr": {"title": "My Favorite anime Movie"}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is True

    def test_contains_no_match(self) -> None:
        """Test contains comparison with non-matching substring."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="title",
            value="documentary",
            operator=PluginMetadataOperator.CONTAINS,
        )
        metadata: PluginMetadataDict = {"radarr": {"title": "My Favorite Anime Movie"}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is False

    def test_lt_integer(self) -> None:
        """Test less-than comparison with integers."""
        condition = PluginMetadataCondition(
            plugin="sonarr",
            field="episode_count",
            value=100,
            operator=PluginMetadataOperator.LT,
        )
        metadata: PluginMetadataDict = {"sonarr": {"episode_count": 50}}

        result, _ = evaluate_plugin_metadata(condition, metadata)
        assert result is True

        # Test with equal value
        metadata["sonarr"]["episode_count"] = 100
        result, _ = evaluate_plugin_metadata(condition, metadata)
        assert result is False

    def test_lte_integer(self) -> None:
        """Test less-than-or-equal comparison with integers."""
        condition = PluginMetadataCondition(
            plugin="sonarr",
            field="episode_count",
            value=100,
            operator=PluginMetadataOperator.LTE,
        )
        metadata: PluginMetadataDict = {"sonarr": {"episode_count": 100}}

        result, _ = evaluate_plugin_metadata(condition, metadata)
        assert result is True

        metadata["sonarr"]["episode_count"] = 101
        result, _ = evaluate_plugin_metadata(condition, metadata)
        assert result is False

    def test_gt_integer(self) -> None:
        """Test greater-than comparison with integers."""
        condition = PluginMetadataCondition(
            plugin="sonarr",
            field="episode_count",
            value=50,
            operator=PluginMetadataOperator.GT,
        )
        metadata: PluginMetadataDict = {"sonarr": {"episode_count": 100}}

        result, _ = evaluate_plugin_metadata(condition, metadata)
        assert result is True

        metadata["sonarr"]["episode_count"] = 50
        result, _ = evaluate_plugin_metadata(condition, metadata)
        assert result is False

    def test_gte_integer(self) -> None:
        """Test greater-than-or-equal comparison with integers."""
        condition = PluginMetadataCondition(
            plugin="sonarr",
            field="episode_count",
            value=50,
            operator=PluginMetadataOperator.GTE,
        )
        metadata: PluginMetadataDict = {"sonarr": {"episode_count": 50}}

        result, _ = evaluate_plugin_metadata(condition, metadata)
        assert result is True

        metadata["sonarr"]["episode_count"] = 49
        result, _ = evaluate_plugin_metadata(condition, metadata)
        assert result is False

    def test_numeric_comparison_with_float(self) -> None:
        """Test numeric comparison with float values."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="rating",
            value=7.5,
            operator=PluginMetadataOperator.GTE,
        )
        metadata: PluginMetadataDict = {"radarr": {"rating": 8.2}}

        result, _ = evaluate_plugin_metadata(condition, metadata)
        assert result is True

    def test_numeric_comparison_with_string_fails(self) -> None:
        """Test numeric comparison returns False when value is string."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="title",
            value=100,
            operator=PluginMetadataOperator.GT,
        )
        metadata: PluginMetadataDict = {"radarr": {"title": "Some Movie"}}

        result, _ = evaluate_plugin_metadata(condition, metadata)
        assert result is False


class TestPluginMetadataValidation:
    """Tests for validation of unknown plugins and fields."""

    def test_no_metadata_available(self) -> None:
        """Test condition returns False with helpful reason when no metadata."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="jpn",
        )

        result, reason = evaluate_plugin_metadata(condition, None)

        assert result is False
        assert "no plugin metadata available" in reason

    def test_plugin_not_in_metadata(self) -> None:
        """Test condition returns False with helpful reason when plugin missing."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="jpn",
        )
        metadata: PluginMetadataDict = {"sonarr": {"series_title": "Some Show"}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is False
        assert "plugin 'radarr' not in metadata" in reason

    def test_field_not_in_plugin_data(self) -> None:
        """Test condition returns False with helpful reason when field missing."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="jpn",
        )
        metadata: PluginMetadataDict = {"radarr": {"title": "Some Movie"}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is False
        assert "field 'original_language' not found" in reason

    def test_field_value_is_null(self) -> None:
        """Test condition returns False when field value is None."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="jpn",
        )
        metadata: PluginMetadataDict = {"radarr": {"original_language": None}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is False
        assert "field value is null" in reason


class TestPluginMetadataConditionDataclass:
    """Tests for PluginMetadataCondition dataclass."""

    def test_default_operator_is_eq(self) -> None:
        """Test default operator is EQ."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="jpn",
        )
        assert condition.operator == PluginMetadataOperator.EQ

    def test_frozen_dataclass(self) -> None:
        """Test dataclass is immutable."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="jpn",
        )
        with pytest.raises(AttributeError):
            condition.plugin = "sonarr"  # type: ignore[misc]

    def test_all_operators_have_values(self) -> None:
        """Test all operators have string values for serialization."""
        expected = {"eq", "neq", "contains", "lt", "lte", "gt", "gte"}
        actual = {op.value for op in PluginMetadataOperator}
        assert actual == expected
