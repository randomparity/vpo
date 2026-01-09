"""Unit tests for plugin metadata condition evaluation (V12)."""

from __future__ import annotations

import pytest

from vpo.policy.conditions import (
    PluginMetadataDict,
    evaluate_plugin_metadata,
)
from vpo.policy.models import (
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


class TestPluginMetadataCaseInsensitivity:
    """Tests for case-insensitive plugin and field lookups."""

    def test_plugin_name_case_insensitive(self) -> None:
        """Test that plugin names are matched case-insensitively."""
        condition = PluginMetadataCondition(
            plugin="radarr",  # lowercase in condition
            field="original_language",
            value="jpn",
            operator=PluginMetadataOperator.EQ,
        )
        # Plugin name in metadata has different case
        metadata: PluginMetadataDict = {"Radarr": {"original_language": "jpn"}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is True
        assert "actual='jpn'" in reason

    def test_field_name_case_insensitive(self) -> None:
        """Test that field names are matched case-insensitively."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",  # lowercase in condition
            value="jpn",
            operator=PluginMetadataOperator.EQ,
        )
        # Field name in metadata has different case
        metadata: PluginMetadataDict = {"radarr": {"Original_Language": "jpn"}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is True
        assert "actual='jpn'" in reason

    def test_both_plugin_and_field_case_insensitive(self) -> None:
        """Test that both plugin and field names are matched case-insensitively."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="eng",
            operator=PluginMetadataOperator.NEQ,
        )
        # Both names have different case in metadata
        metadata: PluginMetadataDict = {"RADARR": {"ORIGINAL_LANGUAGE": "jpn"}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is True  # jpn != eng


class TestExistsOperator:
    """Tests for the EXISTS operator."""

    def test_exists_returns_true_when_field_present(self) -> None:
        """Test EXISTS operator returns True when field is present."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            operator=PluginMetadataOperator.EXISTS,
        )
        metadata: PluginMetadataDict = {"radarr": {"original_language": "jpn"}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is True
        assert "exists → True" in reason

    def test_exists_returns_false_when_field_missing(self) -> None:
        """Test EXISTS operator returns False when field is missing."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            operator=PluginMetadataOperator.EXISTS,
        )
        metadata: PluginMetadataDict = {"radarr": {"title": "Some Movie"}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is False
        assert "not found" in reason

    def test_exists_returns_false_when_plugin_missing(self) -> None:
        """Test EXISTS operator returns False when plugin is missing."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            operator=PluginMetadataOperator.EXISTS,
        )
        metadata: PluginMetadataDict = {"sonarr": {"series_title": "Some Show"}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is False
        assert "plugin 'radarr' not in metadata" in reason


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
        expected = {"eq", "neq", "contains", "lt", "lte", "gt", "gte", "exists"}
        actual = {op.value for op in PluginMetadataOperator}
        assert actual == expected


class TestBooleanPluginMetadata:
    """Tests for boolean values in plugin metadata conditions."""

    def test_eq_boolean_true_match(self) -> None:
        """Test equality comparison with matching boolean True."""
        condition = PluginMetadataCondition(
            plugin="myapp",
            field="is_anime",
            value=True,
            operator=PluginMetadataOperator.EQ,
        )
        metadata: PluginMetadataDict = {"myapp": {"is_anime": True}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is True
        assert "True" in reason

    def test_eq_boolean_false_match(self) -> None:
        """Test equality comparison with matching boolean False."""
        condition = PluginMetadataCondition(
            plugin="myapp",
            field="is_anime",
            value=False,
            operator=PluginMetadataOperator.EQ,
        )
        metadata: PluginMetadataDict = {"myapp": {"is_anime": False}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is True

    def test_eq_boolean_no_match(self) -> None:
        """Test equality comparison with non-matching boolean."""
        condition = PluginMetadataCondition(
            plugin="myapp",
            field="is_anime",
            value=True,
            operator=PluginMetadataOperator.EQ,
        )
        metadata: PluginMetadataDict = {"myapp": {"is_anime": False}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is False

    def test_neq_boolean(self) -> None:
        """Test not-equal comparison with booleans."""
        condition = PluginMetadataCondition(
            plugin="myapp",
            field="is_anime",
            value=False,
            operator=PluginMetadataOperator.NEQ,
        )
        metadata: PluginMetadataDict = {"myapp": {"is_anime": True}}

        result, reason = evaluate_plugin_metadata(condition, metadata)

        assert result is True


class TestNotConditionWithPluginMetadata:
    """Tests for NOT condition wrapping plugin_metadata conditions."""

    def test_not_wrapping_plugin_metadata_true_becomes_false(self) -> None:
        """Test NOT condition inverts a True plugin_metadata result."""
        from vpo.policy.conditions import evaluate_condition
        from vpo.policy.models import NotCondition

        inner_condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="jpn",
            operator=PluginMetadataOperator.EQ,
        )
        not_condition = NotCondition(inner=inner_condition)
        metadata: PluginMetadataDict = {"radarr": {"original_language": "jpn"}}

        result, reason = evaluate_condition(not_condition, [], plugin_metadata=metadata)

        assert result is False  # NOT(True) = False
        assert "not(" in reason  # Uses lowercase "not" in the reason string

    def test_not_wrapping_plugin_metadata_false_becomes_true(self) -> None:
        """Test NOT condition inverts a False plugin_metadata result."""
        from vpo.policy.conditions import evaluate_condition
        from vpo.policy.models import NotCondition

        inner_condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="jpn",
            operator=PluginMetadataOperator.EQ,
        )
        not_condition = NotCondition(inner=inner_condition)
        metadata: PluginMetadataDict = {"radarr": {"original_language": "eng"}}

        result, reason = evaluate_condition(not_condition, [], plugin_metadata=metadata)

        assert result is True  # NOT(False) = True
        assert "not(" in reason  # Uses lowercase "not" in the reason string

    def test_not_wrapping_plugin_metadata_no_metadata(self) -> None:
        """Test NOT condition when plugin_metadata is None (inverts False to True)."""
        from vpo.policy.conditions import evaluate_condition
        from vpo.policy.models import NotCondition

        inner_condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="jpn",
            operator=PluginMetadataOperator.EQ,
        )
        not_condition = NotCondition(inner=inner_condition)

        result, reason = evaluate_condition(not_condition, [], plugin_metadata=None)

        # Inner returns False (no metadata), NOT inverts to True
        assert result is True
