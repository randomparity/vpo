"""Unit tests for plugin metadata condition YAML loading (V12)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vpo.policy.loader import (
    PluginMetadataConditionModel,
    load_policy_from_dict,
)
from vpo.policy.models import (
    PluginMetadataCondition,
    PluginMetadataOperator,
)


class TestPluginMetadataConditionModel:
    """Tests for PluginMetadataConditionModel Pydantic validation."""

    def test_valid_string_condition(self) -> None:
        """Test valid string equality condition."""
        model = PluginMetadataConditionModel(
            plugin="radarr",
            field="original_language",
            value="jpn",
        )
        assert model.plugin == "radarr"
        assert model.field == "original_language"
        assert model.value == "jpn"
        assert model.operator == "eq"

    def test_valid_integer_condition(self) -> None:
        """Test valid integer condition."""
        model = PluginMetadataConditionModel(
            plugin="sonarr",
            field="episode_count",
            value=12,
            operator="gt",
        )
        assert model.value == 12
        assert model.operator == "gt"

    def test_valid_boolean_condition(self) -> None:
        """Test valid boolean condition."""
        model = PluginMetadataConditionModel(
            plugin="radarr",
            field="has_file",
            value=True,
        )
        assert model.value is True

    def test_plugin_name_normalized_to_lowercase(self) -> None:
        """Test plugin name is normalized to lowercase."""
        model = PluginMetadataConditionModel(
            plugin="Radarr",
            field="original_language",
            value="jpn",
        )
        assert model.plugin == "radarr"

    def test_plugin_name_trimmed(self) -> None:
        """Test plugin name is trimmed."""
        model = PluginMetadataConditionModel(
            plugin="  radarr  ",
            field="original_language",
            value="jpn",
        )
        assert model.plugin == "radarr"

    def test_field_name_trimmed(self) -> None:
        """Test field name is trimmed."""
        model = PluginMetadataConditionModel(
            plugin="radarr",
            field="  original_language  ",
            value="jpn",
        )
        assert model.field == "original_language"

    def test_invalid_plugin_name_empty(self) -> None:
        """Test empty plugin name is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PluginMetadataConditionModel(
                plugin="",
                field="original_language",
                value="jpn",
            )
        assert "plugin name cannot be empty" in str(exc_info.value)

    def test_invalid_plugin_name_whitespace(self) -> None:
        """Test whitespace-only plugin name is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PluginMetadataConditionModel(
                plugin="   ",
                field="original_language",
                value="jpn",
            )
        assert "plugin name cannot be empty" in str(exc_info.value)

    def test_invalid_plugin_name_format(self) -> None:
        """Test invalid plugin name format is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PluginMetadataConditionModel(
                plugin="my plugin",  # spaces not allowed
                field="original_language",
                value="jpn",
            )
        assert "Invalid plugin name" in str(exc_info.value)

    def test_invalid_plugin_name_starts_with_number(self) -> None:
        """Test plugin name starting with number is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PluginMetadataConditionModel(
                plugin="123plugin",
                field="original_language",
                value="jpn",
            )
        assert "Invalid plugin name" in str(exc_info.value)

    def test_invalid_field_name_empty(self) -> None:
        """Test empty field name is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PluginMetadataConditionModel(
                plugin="radarr",
                field="",
                value="jpn",
            )
        assert "field name cannot be empty" in str(exc_info.value)

    def test_numeric_operator_requires_numeric_value(self) -> None:
        """Test numeric operators require numeric value."""
        with pytest.raises(ValidationError) as exc_info:
            PluginMetadataConditionModel(
                plugin="radarr",
                field="title",
                value="some string",
                operator="gt",
            )
        assert "requires a numeric value" in str(exc_info.value)

    def test_numeric_operators_accept_integers(self) -> None:
        """Test numeric operators accept integer values."""
        for op in ["lt", "lte", "gt", "gte"]:
            model = PluginMetadataConditionModel(
                plugin="radarr",
                field="year",
                value=2024,
                operator=op,
            )
            assert model.operator == op

    def test_numeric_operators_accept_floats(self) -> None:
        """Test numeric operators accept float values."""
        for op in ["lt", "lte", "gt", "gte"]:
            model = PluginMetadataConditionModel(
                plugin="radarr",
                field="rating",
                value=7.5,
                operator=op,
            )
            assert model.operator == op


class TestPluginMetadataPolicyLoading:
    """Tests for loading policies with plugin_metadata conditions."""

    def test_load_basic_plugin_metadata_condition(self) -> None:
        """Test loading a basic plugin_metadata condition."""
        policy_data = {
            "schema_version": 12,
            "conditional": [
                {
                    "name": "check-anime",
                    "when": {
                        "plugin_metadata": {
                            "plugin": "radarr",
                            "field": "original_language",
                            "value": "jpn",
                        }
                    },
                    "then": {"warn": "Japanese anime detected"},
                }
            ],
        }

        policy = load_policy_from_dict(policy_data)

        assert len(policy.conditional_rules) == 1
        rule = policy.conditional_rules[0]
        assert rule.name == "check-anime"
        assert isinstance(rule.when, PluginMetadataCondition)
        assert rule.when.plugin == "radarr"
        assert rule.when.field == "original_language"
        assert rule.when.value == "jpn"
        assert rule.when.operator == PluginMetadataOperator.EQ

    def test_load_plugin_metadata_with_operator(self) -> None:
        """Test loading plugin_metadata condition with explicit operator."""
        policy_data = {
            "schema_version": 12,
            "conditional": [
                {
                    "name": "check-rating",
                    "when": {
                        "plugin_metadata": {
                            "plugin": "radarr",
                            "field": "rating",
                            "value": 7.0,
                            "operator": "gte",
                        }
                    },
                    "then": {"warn": "High-rated movie"},
                }
            ],
        }

        policy = load_policy_from_dict(policy_data)

        rule = policy.conditional_rules[0]
        assert isinstance(rule.when, PluginMetadataCondition)
        assert rule.when.operator == PluginMetadataOperator.GTE
        assert rule.when.value == 7.0

    def test_load_plugin_metadata_with_contains(self) -> None:
        """Test loading plugin_metadata condition with contains operator."""
        policy_data = {
            "schema_version": 12,
            "conditional": [
                {
                    "name": "check-title",
                    "when": {
                        "plugin_metadata": {
                            "plugin": "radarr",
                            "field": "title",
                            "value": "Extended",
                            "operator": "contains",
                        }
                    },
                    "then": {"warn": "Extended edition"},
                }
            ],
        }

        policy = load_policy_from_dict(policy_data)

        rule = policy.conditional_rules[0]
        assert isinstance(rule.when, PluginMetadataCondition)
        assert rule.when.operator == PluginMetadataOperator.CONTAINS

    def test_load_combined_with_and_condition(self) -> None:
        """Test plugin_metadata in combined AND condition."""
        policy_data = {
            "schema_version": 12,
            "conditional": [
                {
                    "name": "check-anime-with-audio",
                    "when": {
                        "and": [
                            {
                                "plugin_metadata": {
                                    "plugin": "radarr",
                                    "field": "original_language",
                                    "value": "jpn",
                                }
                            },
                            {"exists": {"track_type": "audio", "language": "jpn"}},
                        ]
                    },
                    "then": {"warn": "Japanese anime with Japanese audio"},
                }
            ],
        }

        policy = load_policy_from_dict(policy_data)

        rule = policy.conditional_rules[0]
        # Should be an AND condition containing both sub-conditions
        from vpo.policy.models import AndCondition

        assert isinstance(rule.when, AndCondition)
        assert len(rule.when.conditions) == 2

    def test_load_combined_with_or_condition(self) -> None:
        """Test plugin_metadata in combined OR condition."""
        policy_data = {
            "schema_version": 12,
            "conditional": [
                {
                    "name": "check-arr-metadata",
                    "when": {
                        "or": [
                            {
                                "plugin_metadata": {
                                    "plugin": "radarr",
                                    "field": "original_language",
                                    "value": "jpn",
                                }
                            },
                            {
                                "plugin_metadata": {
                                    "plugin": "sonarr",
                                    "field": "original_language",
                                    "value": "jpn",
                                }
                            },
                        ]
                    },
                    "then": {"warn": "Japanese content from arr metadata"},
                }
            ],
        }

        policy = load_policy_from_dict(policy_data)

        rule = policy.conditional_rules[0]
        from vpo.policy.models import OrCondition

        assert isinstance(rule.when, OrCondition)
        assert len(rule.when.conditions) == 2
