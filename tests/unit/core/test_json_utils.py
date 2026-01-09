"""Tests for vpo.core.json_utils module."""

import pytest
from pydantic import BaseModel, Field

from vpo.core.json_utils import (
    JsonParseResult,
    parse_json_safe,
    parse_json_with_schema,
    serialize_json_safe,
)


class TestJsonParseResult:
    """Tests for JsonParseResult dataclass."""

    def test_success_result(self):
        """Success result has correct attributes."""
        result = JsonParseResult(success=True, value={"key": "value"}, error=None)
        assert result.success is True
        assert result.value == {"key": "value"}
        assert result.error is None

    def test_failure_result(self):
        """Failure result has correct attributes."""
        result = JsonParseResult(success=False, value=None, error="Parse error")
        assert result.success is False
        assert result.value is None
        assert result.error == "Parse error"

    def test_frozen(self):
        """Result is immutable (frozen dataclass)."""
        result = JsonParseResult(success=True, value={}, error=None)
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]


class TestParseJsonSafe:
    """Tests for parse_json_safe function."""

    def test_valid_json_object(self):
        """Valid JSON object parses correctly."""
        result = parse_json_safe('{"name": "test", "count": 42}')
        assert result.success is True
        assert result.value == {"name": "test", "count": 42}
        assert result.error is None

    def test_valid_json_array(self):
        """Valid JSON array parses correctly."""
        result = parse_json_safe("[1, 2, 3]")
        assert result.success is True
        assert result.value == [1, 2, 3]
        assert result.error is None

    def test_invalid_json(self):
        """Invalid JSON returns failure result."""
        result = parse_json_safe('{"unclosed": ')
        assert result.success is False
        assert result.value is None
        assert result.error is not None
        assert "Invalid JSON" in result.error

    def test_invalid_json_with_context(self):
        """Invalid JSON error includes context."""
        result = parse_json_safe("not json", context="summary_json")
        assert result.success is False
        assert "summary_json:" in result.error

    def test_none_input(self):
        """None input returns success with None value."""
        result = parse_json_safe(None)
        assert result.success is True
        assert result.value is None
        assert result.error is None

    def test_empty_string(self):
        """Empty string returns success with None value."""
        result = parse_json_safe("")
        assert result.success is True
        assert result.value is None
        assert result.error is None

    def test_none_input_with_default(self):
        """None input with default returns success with default."""
        result = parse_json_safe(None, default={})
        assert result.success is True
        assert result.value == {}
        assert result.error is None

    def test_empty_string_with_default(self):
        """Empty string with default returns success with default."""
        result = parse_json_safe("", default={"items": []})
        assert result.success is True
        assert result.value == {"items": []}
        assert result.error is None

    def test_invalid_json_with_default(self):
        """Invalid JSON with default returns success with default and error msg."""
        result = parse_json_safe("not json", default={})
        assert result.success is True
        assert result.value == {}
        assert result.error is not None
        assert "Invalid JSON" in result.error

    def test_nested_structure(self):
        """Nested JSON structure parses correctly."""
        json_str = '{"plugin": {"radarr": {"id": 123, "active": true}}}'
        result = parse_json_safe(json_str)
        assert result.success is True
        assert result.value == {"plugin": {"radarr": {"id": 123, "active": True}}}

    def test_unicode_content(self):
        """Unicode content parses correctly."""
        result = parse_json_safe('{"title": "Caf\u00e9 \u2615"}')
        assert result.success is True
        assert result.value == {"title": "Café ☕"}


class SampleSchema(BaseModel):
    """Sample Pydantic model for testing schema validation."""

    name: str
    count: int = Field(ge=0)
    optional_field: str | None = None


class TestParseJsonWithSchema:
    """Tests for parse_json_with_schema function."""

    def test_valid_data(self):
        """Valid data passes schema validation."""
        result = parse_json_with_schema(
            '{"name": "test", "count": 42}',
            SampleSchema,
        )
        assert result.success is True
        assert isinstance(result.value, SampleSchema)
        assert result.value.name == "test"
        assert result.value.count == 42
        assert result.error is None

    def test_missing_required_field(self):
        """Missing required field fails validation."""
        result = parse_json_with_schema(
            '{"count": 42}',  # missing 'name'
            SampleSchema,
        )
        assert result.success is False
        assert result.value is None
        assert "validation failed" in result.error
        assert "name" in result.error

    def test_invalid_field_type(self):
        """Invalid field type fails validation."""
        result = parse_json_with_schema(
            '{"name": "test", "count": "not a number"}',
            SampleSchema,
        )
        assert result.success is False
        assert result.value is None
        assert "validation failed" in result.error

    def test_field_constraint_violation(self):
        """Field constraint violation fails validation."""
        result = parse_json_with_schema(
            '{"name": "test", "count": -1}',  # count must be >= 0
            SampleSchema,
        )
        assert result.success is False
        assert result.value is None
        assert "validation failed" in result.error

    def test_invalid_json(self):
        """Invalid JSON fails before schema validation."""
        result = parse_json_with_schema(
            '{"unclosed": ',
            SampleSchema,
        )
        assert result.success is False
        assert result.value is None
        assert "Invalid JSON" in result.error

    def test_none_input(self):
        """None input returns success with None value."""
        result = parse_json_with_schema(None, SampleSchema)
        assert result.success is True
        assert result.value is None
        assert result.error is None

    def test_empty_string(self):
        """Empty string returns success with None value."""
        result = parse_json_with_schema("", SampleSchema)
        assert result.success is True
        assert result.value is None
        assert result.error is None

    def test_context_in_error(self):
        """Context is included in validation error messages."""
        result = parse_json_with_schema(
            '{"count": 42}',  # missing 'name'
            SampleSchema,
            context="job_summary",
        )
        assert "job_summary:" in result.error

    def test_extra_fields_allowed_by_default(self):
        """Extra fields are allowed by default in Pydantic v2."""
        result = parse_json_with_schema(
            '{"name": "test", "count": 0, "extra": "field"}',
            SampleSchema,
        )
        assert result.success is True
        assert result.value.name == "test"


class TestSerializeJsonSafe:
    """Tests for serialize_json_safe function."""

    def test_serialize_dict(self):
        """Dict serializes to JSON string."""
        result = serialize_json_safe({"key": "value", "number": 42})
        assert result == '{"key": "value", "number": 42}'

    def test_serialize_list(self):
        """List serializes to JSON string."""
        result = serialize_json_safe([1, 2, 3])
        assert result == "[1, 2, 3]"

    def test_serialize_none(self):
        """None input returns None."""
        result = serialize_json_safe(None)
        assert result is None

    def test_serialize_nested(self):
        """Nested structures serialize correctly."""
        data = {"plugins": {"radarr": {"id": 123}}}
        result = serialize_json_safe(data)
        assert result is not None
        # Verify round-trip
        parsed = parse_json_safe(result)
        assert parsed.value == data

    def test_serialize_non_serializable(self):
        """Non-serializable data raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            serialize_json_safe({"func": lambda x: x})  # type: ignore[dict-item]
        assert "Cannot serialize to JSON" in str(exc_info.value)

    def test_serialize_with_context_in_error(self):
        """Context is included in serialization error."""
        with pytest.raises(TypeError) as exc_info:
            serialize_json_safe(
                {"obj": object()},  # type: ignore[dict-item]
                context="plugin_metadata",
            )
        assert "plugin_metadata:" in str(exc_info.value)
