"""Unit tests for container metadata condition evaluation."""

from __future__ import annotations

from vpo.policy.conditions import evaluate_container_metadata
from vpo.policy.types import (
    ContainerMetadataCondition,
    MetadataComparisonOperator,
)


class TestEvaluateContainerMetadata:
    """Tests for evaluate_container_metadata function."""

    def test_eq_match_case_insensitive(self) -> None:
        """EQ comparison is case-insensitive for string values."""
        condition = ContainerMetadataCondition(
            field="title",
            value="My Movie",
            operator=MetadataComparisonOperator.EQ,
        )
        tags = {"title": "my movie"}

        result, reason = evaluate_container_metadata(condition, tags)

        assert result is True
        assert "True" in reason

    def test_eq_no_match(self) -> None:
        """EQ comparison returns False for non-matching strings."""
        condition = ContainerMetadataCondition(
            field="title",
            value="Other Movie",
            operator=MetadataComparisonOperator.EQ,
        )
        tags = {"title": "my movie"}

        result, reason = evaluate_container_metadata(condition, tags)

        assert result is False
        assert "False" in reason

    def test_neq_mismatch(self) -> None:
        """NEQ comparison returns True for different values."""
        condition = ContainerMetadataCondition(
            field="title",
            value="Other Movie",
            operator=MetadataComparisonOperator.NEQ,
        )
        tags = {"title": "my movie"}

        result, reason = evaluate_container_metadata(condition, tags)

        assert result is True

    def test_neq_same_value(self) -> None:
        """NEQ comparison returns False for matching values."""
        condition = ContainerMetadataCondition(
            field="title",
            value="my movie",
            operator=MetadataComparisonOperator.NEQ,
        )
        tags = {"title": "my movie"}

        result, reason = evaluate_container_metadata(condition, tags)

        assert result is False

    def test_contains_substring_match(self) -> None:
        """CONTAINS checks for substring, not regex."""
        condition = ContainerMetadataCondition(
            field="title",
            value="720p",
            operator=MetadataComparisonOperator.CONTAINS,
        )
        tags = {"title": "my movie 720p bluray"}

        result, reason = evaluate_container_metadata(condition, tags)

        assert result is True

    def test_contains_no_match(self) -> None:
        """CONTAINS returns False when substring not found."""
        condition = ContainerMetadataCondition(
            field="title",
            value="1080p",
            operator=MetadataComparisonOperator.CONTAINS,
        )
        tags = {"title": "my movie 720p bluray"}

        result, reason = evaluate_container_metadata(condition, tags)

        assert result is False

    def test_exists_present_field(self) -> None:
        """EXISTS returns True when field is present."""
        condition = ContainerMetadataCondition(
            field="encoder",
            operator=MetadataComparisonOperator.EXISTS,
        )
        tags = {"encoder": "libx265"}

        result, reason = evaluate_container_metadata(condition, tags)

        assert result is True
        assert "exists" in reason

    def test_exists_absent_field(self) -> None:
        """EXISTS returns False when field is absent."""
        condition = ContainerMetadataCondition(
            field="encoder",
            operator=MetadataComparisonOperator.EXISTS,
        )
        tags = {"title": "my movie"}

        result, reason = evaluate_container_metadata(condition, tags)

        assert result is False
        assert "not found" in reason

    def test_lt_numeric_coercion(self) -> None:
        """LT operator coerces string tag values to numbers."""
        condition = ContainerMetadataCondition(
            field="bitrate",
            value=5000,
            operator=MetadataComparisonOperator.LT,
        )
        tags = {"bitrate": "3000"}

        result, reason = evaluate_container_metadata(condition, tags)

        assert result is True

    def test_gt_numeric_coercion(self) -> None:
        """GT operator coerces string tag values to numbers."""
        condition = ContainerMetadataCondition(
            field="bitrate",
            value=2000,
            operator=MetadataComparisonOperator.GT,
        )
        tags = {"bitrate": "3000"}

        result, reason = evaluate_container_metadata(condition, tags)

        assert result is True

    def test_lte_numeric_equal(self) -> None:
        """LTE returns True when values are equal."""
        condition = ContainerMetadataCondition(
            field="bitrate",
            value=3000,
            operator=MetadataComparisonOperator.LTE,
        )
        tags = {"bitrate": "3000"}

        result, reason = evaluate_container_metadata(condition, tags)

        assert result is True

    def test_gte_numeric_less(self) -> None:
        """GTE returns False when actual is less than expected."""
        condition = ContainerMetadataCondition(
            field="bitrate",
            value=5000,
            operator=MetadataComparisonOperator.GTE,
        )
        tags = {"bitrate": "3000"}

        result, reason = evaluate_container_metadata(condition, tags)

        assert result is False

    def test_numeric_op_non_numeric_string_returns_false(self) -> None:
        """Numeric ops return False with reason for non-numeric values."""
        condition = ContainerMetadataCondition(
            field="encoder",
            value=5000,
            operator=MetadataComparisonOperator.GT,
        )
        tags = {"encoder": "libx265"}

        result, reason = evaluate_container_metadata(condition, tags)

        assert result is False
        assert "is not numeric" in reason

    def test_none_container_tags_returns_false(self) -> None:
        """Returns False when container_tags is None."""
        condition = ContainerMetadataCondition(
            field="title",
            value="test",
            operator=MetadataComparisonOperator.EQ,
        )

        result, reason = evaluate_container_metadata(condition, None)

        assert result is False
        assert "no container tags" in reason

    def test_missing_field_returns_false(self) -> None:
        """Returns False when field is not in tags."""
        condition = ContainerMetadataCondition(
            field="missing_field",
            value="test",
            operator=MetadataComparisonOperator.EQ,
        )
        tags = {"title": "my movie"}

        result, reason = evaluate_container_metadata(condition, tags)

        assert result is False
        assert "not found" in reason

    def test_field_lookup_is_case_insensitive(self) -> None:
        """Field lookup works with casefolded keys (parser normalizes to lowercase)."""
        condition = ContainerMetadataCondition(
            field="TITLE",  # uppercase
            value="my movie",
            operator=MetadataComparisonOperator.EQ,
        )
        # Parser output has lowercase keys
        tags = {"title": "my movie"}

        result, reason = evaluate_container_metadata(condition, tags)

        assert result is True
