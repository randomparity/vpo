"""Unit tests for container metadata pydantic models and conversion."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vpo.policy.conversion import (
    _METADATA_OPERATOR_MAP,
    _convert_container_metadata_condition,
)
from vpo.policy.pydantic_models.actions import SetContainerMetadataActionModel
from vpo.policy.pydantic_models.conditions import ContainerMetadataConditionModel
from vpo.policy.types import PluginMetadataOperator


class TestContainerMetadataConditionModel:
    """Tests for ContainerMetadataConditionModel validation."""

    def test_valid_eq_condition(self) -> None:
        """Valid condition with eq operator."""
        model = ContainerMetadataConditionModel(
            field="title",
            value="My Movie",
            operator="eq",
        )
        assert model.field == "title"
        assert model.value == "My Movie"
        assert model.operator == "eq"

    def test_valid_contains_condition(self) -> None:
        """Valid condition with contains operator."""
        model = ContainerMetadataConditionModel(
            field="title",
            value="720p",
            operator="contains",
        )
        assert model.operator == "contains"

    def test_valid_exists_without_value(self) -> None:
        """EXISTS operator does not require a value."""
        model = ContainerMetadataConditionModel(
            field="encoder",
            operator="exists",
        )
        assert model.value is None

    def test_non_exists_without_value_raises(self) -> None:
        """Non-exists operator without value raises ValidationError."""
        with pytest.raises(ValidationError, match="requires a value"):
            ContainerMetadataConditionModel(
                field="title",
                operator="eq",
            )

    def test_numeric_operator_with_string_value_raises(self) -> None:
        """Numeric operator with string value raises ValidationError."""
        with pytest.raises(ValidationError, match="requires a numeric value"):
            ContainerMetadataConditionModel(
                field="bitrate",
                value="not_a_number",
                operator="gt",
            )

    def test_numeric_operator_with_numeric_value(self) -> None:
        """Numeric operator with numeric value is valid."""
        model = ContainerMetadataConditionModel(
            field="bitrate",
            value=5000,
            operator="gt",
        )
        assert model.value == 5000

    def test_empty_field_name_raises(self) -> None:
        """Empty field name raises ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            ContainerMetadataConditionModel(
                field="",
                value="test",
                operator="eq",
            )

    def test_whitespace_only_field_name_raises(self) -> None:
        """Whitespace-only field name raises ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            ContainerMetadataConditionModel(
                field="   ",
                value="test",
                operator="eq",
            )

    def test_field_name_normalized_to_casefold(self) -> None:
        """Field name is normalized to casefolded form."""
        model = ContainerMetadataConditionModel(
            field="  TITLE  ",
            value="test",
            operator="eq",
        )
        assert model.field == "title"

    def test_field_name_starting_with_digit_raises(self) -> None:
        """Field name starting with digit is rejected."""
        with pytest.raises(ValidationError, match="Invalid field name"):
            ContainerMetadataConditionModel(
                field="123bad",
                value="test",
                operator="eq",
            )

    def test_field_name_with_spaces_raises(self) -> None:
        """Field name with spaces is rejected."""
        with pytest.raises(ValidationError, match="Invalid field name"):
            ContainerMetadataConditionModel(
                field="foo bar",
                value="test",
                operator="eq",
            )

    def test_field_name_too_long_raises(self) -> None:
        """Field name exceeding 64 characters is rejected."""
        with pytest.raises(ValidationError, match="Invalid field name"):
            ContainerMetadataConditionModel(
                field="x" * 65,
                value="test",
                operator="eq",
            )

    def test_field_name_with_special_chars_raises(self) -> None:
        """Field name with special characters is rejected."""
        with pytest.raises(ValidationError, match="Invalid field name"):
            ContainerMetadataConditionModel(
                field="field=evil",
                value="test",
                operator="eq",
            )


class TestSetContainerMetadataActionModel:
    """Tests for SetContainerMetadataActionModel validation."""

    def test_valid_static_value(self) -> None:
        """Valid action with static value."""
        model = SetContainerMetadataActionModel(
            field="title",
            value="My Movie",
        )
        assert model.field == "title"
        assert model.value == "My Movie"

    def test_valid_dynamic_value(self) -> None:
        """Valid action with from_plugin_metadata."""
        model = SetContainerMetadataActionModel(
            field="title",
            from_plugin_metadata={"plugin": "radarr", "field": "title"},
        )
        assert model.from_plugin_metadata is not None

    def test_both_value_and_from_plugin_metadata_raises(self) -> None:
        """Specifying both value and from_plugin_metadata raises."""
        with pytest.raises(ValidationError, match="cannot specify both"):
            SetContainerMetadataActionModel(
                field="title",
                value="static",
                from_plugin_metadata={"plugin": "radarr", "field": "title"},
            )

    def test_neither_value_nor_from_plugin_metadata_raises(self) -> None:
        """Specifying neither value source raises."""
        with pytest.raises(ValidationError, match="must specify either"):
            SetContainerMetadataActionModel(
                field="title",
            )

    def test_empty_field_name_raises(self) -> None:
        """Empty field name raises ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            SetContainerMetadataActionModel(
                field="",
                value="test",
            )

    def test_whitespace_only_field_name_raises(self) -> None:
        """Whitespace-only field name raises ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            SetContainerMetadataActionModel(
                field="   ",
                value="test",
            )

    def test_field_name_normalized_to_casefold(self) -> None:
        """Field name is casefolded."""
        model = SetContainerMetadataActionModel(
            field="  TITLE  ",
            value="test",
        )
        assert model.field == "title"

    def test_field_name_starting_with_digit_raises(self) -> None:
        """Field name starting with digit is rejected."""
        with pytest.raises(ValidationError, match="Invalid field name"):
            SetContainerMetadataActionModel(
                field="123bad",
                value="test",
            )

    def test_field_name_with_special_chars_raises(self) -> None:
        """Field name with special characters is rejected."""
        with pytest.raises(ValidationError, match="Invalid field name"):
            SetContainerMetadataActionModel(
                field="field=evil",
                value="test",
            )


class TestConvertContainerMetadataCondition:
    """Tests for _convert_container_metadata_condition."""

    def test_converts_eq_operator(self) -> None:
        """Converts eq operator correctly."""
        model = ContainerMetadataConditionModel(
            field="title", value="test", operator="eq"
        )
        result = _convert_container_metadata_condition(model)
        assert result.operator == PluginMetadataOperator.EQ

    def test_converts_all_operators(self) -> None:
        """All operators in _METADATA_OPERATOR_MAP convert correctly."""
        for op_str, op_enum in _METADATA_OPERATOR_MAP.items():
            if op_str in ("lt", "lte", "gt", "gte"):
                model = ContainerMetadataConditionModel(
                    field="bitrate", value=5000, operator=op_str
                )
            elif op_str == "exists":
                model = ContainerMetadataConditionModel(
                    field="encoder", operator=op_str
                )
            else:
                model = ContainerMetadataConditionModel(
                    field="title", value="test", operator=op_str
                )
            result = _convert_container_metadata_condition(model)
            assert result.operator == op_enum

    def test_preserves_field_and_value(self) -> None:
        """Conversion preserves field name and value."""
        model = ContainerMetadataConditionModel(
            field="title", value="My Movie", operator="contains"
        )
        result = _convert_container_metadata_condition(model)
        assert result.field == "title"
        assert result.value == "My Movie"
