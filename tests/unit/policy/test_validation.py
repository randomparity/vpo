"""Unit tests for policy validation helpers.

Feature: 025-policy-validation
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from vpo.policy.pydantic_models import PolicyModel
from vpo.policy.validation import (
    DiffSummary,
    FieldChange,
    ValidationError,
    ValidationResult,
    format_pydantic_errors,
    validate_policy_data,
)


class TestValidationError:
    """Tests for ValidationError dataclass."""

    def test_to_dict_basic(self):
        """Test basic serialization."""
        error = ValidationError(field="track_order", message="Cannot be empty")
        result = error.to_dict()
        assert result == {"field": "track_order", "message": "Cannot be empty"}

    def test_to_dict_with_code(self):
        """Test serialization with error code."""
        error = ValidationError(
            field="audio_language_preference[0]",
            message="Invalid language code",
            code="string_pattern_mismatch",
        )
        result = error.to_dict()
        assert result == {
            "field": "audio_language_preference[0]",
            "message": "Invalid language code",
            "code": "string_pattern_mismatch",
        }

    def test_to_dict_code_none_excluded(self):
        """Test that None code is excluded from dict."""
        error = ValidationError(field="test", message="Test message", code=None)
        result = error.to_dict()
        assert "code" not in result


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_success_result(self):
        """Test successful validation result."""
        result = ValidationResult(success=True, errors=[], policy={"key": "value"})
        assert result.success is True
        assert result.errors == []
        assert result.policy == {"key": "value"}

    def test_failure_result(self):
        """Test failed validation result."""
        errors = [ValidationError(field="test", message="Failed")]
        result = ValidationResult(success=False, errors=errors, policy=None)
        assert result.success is False
        assert len(result.errors) == 1
        assert result.policy is None

    def test_to_dict_success(self):
        """Test dict serialization for success."""
        result = ValidationResult(success=True, policy={"schema_version": 12})
        d = result.to_dict()
        assert d["success"] is True
        assert d["policy"] == {"schema_version": 12}
        assert "errors" not in d  # Empty errors should be excluded

    def test_to_dict_failure(self):
        """Test dict serialization for failure."""
        errors = [ValidationError(field="test", message="Error")]
        result = ValidationResult(success=False, errors=errors)
        d = result.to_dict()
        assert d["success"] is False
        assert len(d["errors"]) == 1
        assert d["errors"][0]["field"] == "test"


class TestFormatPydanticErrors:
    """Tests for format_pydantic_errors function."""

    def test_single_field_error(self):
        """Test converting a single field error."""
        # Create a Pydantic error by validating invalid data
        try:
            PolicyModel.model_validate(
                {
                    "schema_version": 12,
                    "phases": [
                        {
                            "name": "test",
                            "track_order": [],  # Invalid: cannot be empty
                        }
                    ],
                }
            )
            pytest.fail("Expected validation error")
        except PydanticValidationError as e:
            errors = format_pydantic_errors(e)

        assert len(errors) >= 1
        # Find the track_order error
        track_error = next((e for e in errors if "track_order" in e.field), None)
        assert track_error is not None
        assert "empty" in track_error.message.lower()

    def test_array_index_in_path(self):
        """Test that array indices are included in field path or message."""
        try:
            PolicyModel.model_validate(
                {
                    "schema_version": 12,
                    "config": {
                        "audio_language_preference": [
                            "english"
                        ],  # Invalid: not ISO 639-2
                    },
                    "phases": [{"name": "test"}],
                }
            )
            pytest.fail("Expected validation error")
        except PydanticValidationError as e:
            errors = format_pydantic_errors(e)

        assert len(errors) >= 1
        # Find the language error
        lang_error = next(
            (e for e in errors if "audio_language_preference" in e.field), None
        )
        assert lang_error is not None
        # The index is included in the error message (index 0)
        assert "index 0" in lang_error.message or "[0]" in lang_error.field

    def test_multiple_errors(self):
        """Test handling multiple validation errors."""
        try:
            PolicyModel.model_validate(
                {
                    "schema_version": 12,
                    "config": {
                        "audio_language_preference": ["invalid_lang_code"],  # Invalid
                        "subtitle_language_preference": ["also_invalid"],  # Invalid
                    },
                    "phases": [
                        {
                            "name": "test",
                            "track_order": [],  # Invalid
                        }
                    ],
                }
            )
            pytest.fail("Expected validation error")
        except PydanticValidationError as e:
            errors = format_pydantic_errors(e)

        # Should have multiple errors
        assert len(errors) >= 2

    def test_error_code_preserved(self):
        """Test that error type code is preserved."""
        try:
            PolicyModel.model_validate(
                {
                    "schema_version": 12,
                    "config": {
                        "audio_language_preference": ["toolongcode"],  # Invalid pattern
                    },
                    "phases": [{"name": "test"}],
                }
            )
            pytest.fail("Expected validation error")
        except PydanticValidationError as e:
            errors = format_pydantic_errors(e)

        assert len(errors) >= 1
        # At least one error should have a code
        error_with_code = next((e for e in errors if e.code is not None), None)
        assert error_with_code is not None


class TestValidatePolicyData:
    """Tests for validate_policy_data function."""

    def test_valid_policy(self):
        """Test validation of valid policy data."""
        data = {
            "schema_version": 12,
            "config": {
                "audio_language_preference": ["eng", "jpn"],
                "subtitle_language_preference": ["eng"],
            },
            "phases": [
                {
                    "name": "organize",
                    "track_order": ["video", "audio_main"],
                    "default_flags": {
                        "set_first_video_default": True,
                        "set_preferred_audio_default": True,
                        "set_preferred_subtitle_default": False,
                        "clear_other_defaults": True,
                    },
                }
            ],
        }
        result = validate_policy_data(data)

        assert result.success is True
        assert len(result.errors) == 0
        assert result.policy is not None
        assert result.policy["schema_version"] == 12

    def test_invalid_empty_track_order(self):
        """Test validation fails for empty track_order."""
        data = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "test",
                    "track_order": [],  # Invalid: empty
                }
            ],
        }
        result = validate_policy_data(data)

        assert result.success is False
        assert len(result.errors) >= 1
        assert result.policy is None

    def test_invalid_language_code(self):
        """Test validation fails for invalid language code."""
        data = {
            "schema_version": 12,
            "config": {
                "audio_language_preference": ["english"],  # Invalid
            },
            "phases": [{"name": "test"}],
        }
        result = validate_policy_data(data)

        assert result.success is False
        # Should have error mentioning the language issue
        lang_error = next(
            (e for e in result.errors if "audio_language_preference" in e.field), None
        )
        assert lang_error is not None

    def test_invalid_regex_pattern(self):
        """Test validation fails for invalid regex pattern."""
        data = {
            "schema_version": 12,
            "config": {
                "commentary_patterns": ["[invalid("],  # Invalid regex
            },
            "phases": [{"name": "test"}],
        }
        result = validate_policy_data(data)

        assert result.success is False
        assert len(result.errors) >= 1

    def test_empty_language_preference_accepted(self):
        """Test validation accepts empty language preference (uses defaults)."""
        data = {
            "schema_version": 12,
            "config": {
                "audio_language_preference": [],  # Empty - will use defaults
            },
            "phases": [{"name": "test"}],
        }
        result = validate_policy_data(data)

        # Empty lists are valid - the model will use defaults internally
        assert result.success is True
        assert result.policy is not None


class TestDiffSummary:
    """Tests for DiffSummary class."""

    def test_no_changes(self):
        """Test comparison with identical data."""
        data = {"track_order": ["video", "audio_main"]}
        diff = DiffSummary.compare_policies(data, data)
        assert len(diff.changes) == 0
        assert diff.to_summary_text() == "No changes"

    def test_list_reorder(self):
        """Test detection of list reordering."""
        old = {"audio_language_preference": ["eng", "jpn"]}
        new = {"audio_language_preference": ["jpn", "eng"]}
        diff = DiffSummary.compare_policies(old, new)

        assert len(diff.changes) == 1
        assert diff.changes[0].field == "audio_language_preference"
        assert diff.changes[0].change_type == "reordered"
        assert "eng, jpn" in diff.changes[0].details
        assert "jpn, eng" in diff.changes[0].details

    def test_list_items_added(self):
        """Test detection of items added to list."""
        old = {"audio_language_preference": ["eng"]}
        new = {"audio_language_preference": ["eng", "jpn"]}
        diff = DiffSummary.compare_policies(old, new)

        assert len(diff.changes) == 1
        assert diff.changes[0].change_type == "items_added"
        assert "jpn" in diff.changes[0].details

    def test_list_items_removed(self):
        """Test detection of items removed from list."""
        old = {"audio_language_preference": ["eng", "jpn"]}
        new = {"audio_language_preference": ["eng"]}
        diff = DiffSummary.compare_policies(old, new)

        assert len(diff.changes) == 1
        assert diff.changes[0].change_type == "items_removed"
        assert "jpn" in diff.changes[0].details

    def test_dict_single_key_modified(self):
        """Test detection of single key change in dict."""
        old = {"default_flags": {"set_first_video_default": True}}
        new = {"default_flags": {"set_first_video_default": False}}
        diff = DiffSummary.compare_policies(old, new)

        assert len(diff.changes) == 1
        assert diff.changes[0].field == "default_flags.set_first_video_default"
        assert diff.changes[0].change_type == "modified"
        assert "True" in diff.changes[0].details
        assert "False" in diff.changes[0].details

    def test_dict_multiple_keys_modified(self):
        """Test detection of multiple keys changed in dict."""
        old = {"default_flags": {"a": True, "b": True}}
        new = {"default_flags": {"a": False, "b": False}}
        diff = DiffSummary.compare_policies(old, new)

        assert len(diff.changes) == 1
        assert diff.changes[0].field == "default_flags"
        assert diff.changes[0].change_type == "modified"
        assert "a" in diff.changes[0].details
        assert "b" in diff.changes[0].details

    def test_field_added(self):
        """Test detection of new field added."""
        old = {}
        new = {"track_order": ["video"]}
        diff = DiffSummary.compare_policies(old, new)

        assert len(diff.changes) == 1
        assert diff.changes[0].change_type == "added"

    def test_field_removed(self):
        """Test detection of field removed."""
        old = {"track_order": ["video"]}
        new = {}
        diff = DiffSummary.compare_policies(old, new)

        assert len(diff.changes) == 1
        assert diff.changes[0].change_type == "removed"

    def test_to_summary_text_multiple_changes(self):
        """Test summary text with multiple changes."""
        old = {
            "track_order": ["video", "audio_main"],
            "audio_language_preference": ["eng"],
        }
        new = {
            "track_order": ["audio_main", "video"],
            "audio_language_preference": ["eng", "jpn"],
        }
        diff = DiffSummary.compare_policies(old, new)

        summary = diff.to_summary_text()
        assert "track_order" in summary
        assert "audio_language_preference" in summary

    def test_compare_with_commentary_patterns(self):
        """Test comparison of commentary_patterns field."""
        old = {"commentary_patterns": ["commentary"]}
        new = {"commentary_patterns": ["commentary", "director"]}
        diff = DiffSummary.compare_policies(old, new)

        assert len(diff.changes) == 1
        assert diff.changes[0].field == "commentary_patterns"
        assert diff.changes[0].change_type == "items_added"


class TestFieldChange:
    """Tests for FieldChange dataclass."""

    def test_to_dict_basic(self):
        """Test basic serialization."""
        change = FieldChange(field="track_order", change_type="modified")
        result = change.to_dict()
        assert result == {"field": "track_order", "change_type": "modified"}

    def test_to_dict_with_details(self):
        """Test serialization with details."""
        change = FieldChange(
            field="audio_language_preference",
            change_type="reordered",
            details="eng, jpn -> jpn, eng",
        )
        result = change.to_dict()
        assert result["details"] == "eng, jpn -> jpn, eng"

    def test_to_dict_details_none_excluded(self):
        """Test that None details is excluded from dict."""
        change = FieldChange(field="test", change_type="added", details=None)
        result = change.to_dict()
        assert "details" not in result
