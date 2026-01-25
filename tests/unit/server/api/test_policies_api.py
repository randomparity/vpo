"""Unit tests for server/api/policies.py.

Tests the policies API handlers and validation:
- Policy name format validation
- Path traversal prevention
- Validation error response formatting
- Policy editor models
"""

from __future__ import annotations

import re

import pytest

from vpo.server.ui.models import (
    ChangedFieldItem,
    PolicyEditorContext,
    PolicyEditorRequest,
    PolicySaveSuccessResponse,
    PolicyValidateResponse,
    ValidationErrorItem,
    ValidationErrorResponse,
)

# =============================================================================
# Tests for policy name validation
# =============================================================================


class TestPolicyNameValidation:
    """Tests for policy name format validation."""

    # Pattern used in policies.py for name validation
    NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

    def test_allows_alphanumeric(self):
        """Allows simple alphanumeric names."""
        assert self.NAME_PATTERN.match("default")
        assert self.NAME_PATTERN.match("policy1")
        assert self.NAME_PATTERN.match("MyPolicy")

    def test_allows_dashes(self):
        """Allows dashes in policy names."""
        assert self.NAME_PATTERN.match("my-policy")
        assert self.NAME_PATTERN.match("default-video")

    def test_allows_underscores(self):
        """Allows underscores in policy names."""
        assert self.NAME_PATTERN.match("my_policy")
        assert self.NAME_PATTERN.match("default_video_settings")

    def test_allows_mixed_characters(self):
        """Allows mixed alphanumeric, dashes, and underscores."""
        assert self.NAME_PATTERN.match("my-policy_v2")
        assert self.NAME_PATTERN.match("policy-123_test")

    def test_rejects_path_traversal_chars(self):
        """Rejects characters used in path traversal."""
        assert self.NAME_PATTERN.match("..") is None
        assert self.NAME_PATTERN.match("../evil") is None
        assert self.NAME_PATTERN.match("policy/subdir") is None
        assert self.NAME_PATTERN.match("policy\\subdir") is None

    def test_rejects_special_characters(self):
        """Rejects special characters not in allowed set."""
        assert self.NAME_PATTERN.match("policy.yaml") is None
        assert self.NAME_PATTERN.match("policy name") is None
        assert self.NAME_PATTERN.match("policy@test") is None
        assert self.NAME_PATTERN.match("policy#1") is None

    def test_rejects_empty_string(self):
        """Rejects empty string."""
        assert self.NAME_PATTERN.match("") is None


# =============================================================================
# Tests for ValidationErrorItem and ValidationErrorResponse
# =============================================================================


class TestValidationErrorItem:
    """Tests for ValidationErrorItem.to_dict() method."""

    def test_to_dict_basic(self):
        """Serializes validation error item."""
        item = ValidationErrorItem(
            field="schema_version",
            message="Invalid schema version",
            code="invalid_version",
        )

        result = item.to_dict()

        assert result["field"] == "schema_version"
        assert result["message"] == "Invalid schema version"
        assert result["code"] == "invalid_version"

    def test_to_dict_excludes_none_code(self):
        """Code field is excluded when None."""
        item = ValidationErrorItem(
            field="track_order",
            message="Must be a list",
            code=None,
        )

        result = item.to_dict()

        assert result["field"] == "track_order"
        assert "code" not in result


class TestValidationErrorResponse:
    """Tests for ValidationErrorResponse.to_dict() method."""

    def test_to_dict_single_error(self):
        """Serializes response with single error."""
        error = ValidationErrorItem(
            field="phases",
            message="Required field",
            code="required",
        )
        response = ValidationErrorResponse(
            error="Validation failed",
            errors=[error],
            details="1 validation error(s) found",
        )

        result = response.to_dict()

        assert result["error"] == "Validation failed"
        assert len(result["errors"]) == 1
        assert result["errors"][0]["field"] == "phases"
        assert result["details"] == "1 validation error(s) found"

    def test_to_dict_multiple_errors(self):
        """Serializes response with multiple errors."""
        errors = [
            ValidationErrorItem(field="phases", message="Required", code="required"),
            ValidationErrorItem(
                field="schema_version", message="Invalid", code="invalid"
            ),
        ]
        response = ValidationErrorResponse(
            error="Validation failed",
            errors=errors,
            details="2 validation error(s) found",
        )

        result = response.to_dict()

        assert len(result["errors"]) == 2


# =============================================================================
# Tests for PolicyValidateResponse
# =============================================================================


class TestPolicyValidateResponse:
    """Tests for PolicyValidateResponse.to_dict() method."""

    def test_to_dict_valid(self):
        """Serializes valid policy response (no errors field)."""
        response = PolicyValidateResponse(
            valid=True,
            errors=[],
            message="Policy configuration is valid",
        )

        result = response.to_dict()

        assert result["valid"] is True
        assert result["message"] == "Policy configuration is valid"
        # Empty errors list is omitted from output
        assert "errors" not in result

    def test_to_dict_invalid(self):
        """Serializes invalid policy response with errors."""
        errors = [
            ValidationErrorItem(field="phases", message="Required", code="required")
        ]
        response = PolicyValidateResponse(
            valid=False,
            errors=errors,
            message="1 validation error(s) found",
        )

        result = response.to_dict()

        assert result["valid"] is False
        assert len(result["errors"]) == 1


# =============================================================================
# Tests for PolicyEditorRequest
# =============================================================================


class TestPolicyEditorRequest:
    """Tests for PolicyEditorRequest model."""

    def test_from_dict_with_phases(self):
        """Creates request with phases configuration."""
        data = {
            "last_modified_timestamp": "2024-01-15T10:00:00Z",
            "phases": [{"name": "normalize", "container": {"target": "mkv"}}],
        }

        request = PolicyEditorRequest.from_dict(data)

        assert request.phases is not None
        assert len(request.phases) == 1
        assert request.phases[0]["name"] == "normalize"
        assert request.last_modified_timestamp == "2024-01-15T10:00:00Z"

    def test_from_dict_raises_without_last_modified(self):
        """Raises ValueError when last_modified_timestamp missing."""
        data = {
            "phases": [{"name": "normalize"}],
        }

        with pytest.raises(ValueError) as exc_info:
            PolicyEditorRequest.from_dict(data)

        assert "last_modified_timestamp" in str(exc_info.value)

    def test_from_dict_legacy_format(self):
        """Creates request from legacy flat format."""
        data = {
            "last_modified_timestamp": "2024-01-15T10:00:00Z",
            "track_order": ["video", "audio"],
            "audio_language_preference": ["eng"],
            "subtitle_language_preference": ["eng"],
            "commentary_patterns": [],
            "default_flags": {},
        }

        request = PolicyEditorRequest.from_dict(data)

        assert request.track_order == ["video", "audio"]
        assert request.audio_language_preference == ["eng"]

    def test_to_policy_dict_phased_format(self):
        """to_policy_dict produces phased format when phases present."""
        data = {
            "last_modified_timestamp": "2024-01-15T10:00:00Z",
            "phases": [{"name": "normalize", "container": {"target": "mkv"}}],
            "config": {"on_error": "skip"},
        }
        request = PolicyEditorRequest.from_dict(data)

        policy_dict = request.to_policy_dict()

        assert policy_dict["schema_version"] == 12
        assert policy_dict["phases"] == [
            {"name": "normalize", "container": {"target": "mkv"}}
        ]
        assert policy_dict["config"] == {"on_error": "skip"}

    def test_to_policy_dict_excludes_none_values(self):
        """to_policy_dict excludes None optional values."""
        data = {
            "last_modified_timestamp": "2024-01-15T10:00:00Z",
            "track_order": ["video"],
            "audio_language_preference": ["eng"],
            "subtitle_language_preference": ["eng"],
            "commentary_patterns": [],
            "default_flags": {},
            "transcode": None,
        }
        request = PolicyEditorRequest.from_dict(data)

        policy_dict = request.to_policy_dict()

        # None values should not be included
        assert "transcode" not in policy_dict


# =============================================================================
# Tests for ChangedFieldItem
# =============================================================================


class TestChangedFieldItem:
    """Tests for ChangedFieldItem.to_dict() method."""

    def test_to_dict_added_field(self):
        """Serializes added field change."""
        item = ChangedFieldItem(
            field="phases",
            change_type="added",
            details="Added 2 phases",
        )

        result = item.to_dict()

        assert result["field"] == "phases"
        assert result["change_type"] == "added"
        assert result["details"] == "Added 2 phases"

    def test_to_dict_modified_field(self):
        """Serializes modified field change."""
        item = ChangedFieldItem(
            field="track_order",
            change_type="modified",
            details="Changed order",
        )

        result = item.to_dict()

        assert result["change_type"] == "modified"

    def test_to_dict_excludes_none_details(self):
        """Details field is excluded when None."""
        item = ChangedFieldItem(
            field="transcode",
            change_type="removed",
            details=None,
        )

        result = item.to_dict()

        assert result["change_type"] == "removed"
        assert "details" not in result


# =============================================================================
# Tests for PolicySaveSuccessResponse
# =============================================================================


class TestPolicySaveSuccessResponse:
    """Tests for PolicySaveSuccessResponse.to_dict() method."""

    def test_to_dict_with_changes(self):
        """Serializes successful save response with changes."""
        changes = [
            ChangedFieldItem(field="phases", change_type="added", details="1 phase"),
        ]
        policy_context = PolicyEditorContext(
            name="test",
            filename="test.yaml",
            file_path="/policies/test.yaml",
            last_modified="2024-01-15T10:00:00Z",
            schema_version=12,
            track_order=["video", "audio"],
            audio_language_preference=["eng"],
            subtitle_language_preference=["eng"],
            commentary_patterns=[],
            default_flags={},
            transcode=None,
            transcription=None,
        )
        response = PolicySaveSuccessResponse(
            success=True,
            changed_fields=changes,
            changed_fields_summary="1 field changed",
            policy=policy_context.to_dict(),
        )

        result = response.to_dict()

        assert result["success"] is True
        assert len(result["changed_fields"]) == 1
        assert result["changed_fields_summary"] == "1 field changed"
        # Policy fields are spread at top level
        assert result["name"] == "test"


# =============================================================================
# Tests for PolicyEditorContext
# =============================================================================


class TestPolicyEditorContext:
    """Tests for PolicyEditorContext.to_dict() method."""

    def test_to_dict_minimal(self):
        """Serializes minimal policy context."""
        context = PolicyEditorContext(
            name="test",
            filename="test.yaml",
            file_path="/policies/test.yaml",
            last_modified="2024-01-15T10:00:00Z",
            schema_version=12,
            track_order=["video", "audio"],
            audio_language_preference=["eng"],
            subtitle_language_preference=["eng"],
            commentary_patterns=[],
            default_flags={},
            transcode=None,
            transcription=None,
        )

        result = context.to_dict()

        assert result["name"] == "test"
        assert result["filename"] == "test.yaml"
        assert result["schema_version"] == 12
        assert result["track_order"] == ["video", "audio"]

    def test_to_dict_with_v3_fields(self):
        """Serializes context with V3+ filter fields."""
        context = PolicyEditorContext(
            name="test",
            filename="test.yaml",
            file_path="/policies/test.yaml",
            last_modified="2024-01-15T10:00:00Z",
            schema_version=12,
            track_order=[],
            audio_language_preference=[],
            subtitle_language_preference=[],
            commentary_patterns=[],
            default_flags={},
            transcode=None,
            transcription=None,
            audio_filter={"include_languages": ["eng", "jpn"]},
            subtitle_filter={"include_languages": ["eng"]},
            container={"target": "mkv"},
        )

        result = context.to_dict()

        assert result["audio_filter"] == {"include_languages": ["eng", "jpn"]}
        assert result["subtitle_filter"] == {"include_languages": ["eng"]}
        assert result["container"] == {"target": "mkv"}

    def test_to_dict_with_phases(self):
        """Serializes context with phased policy fields."""
        context = PolicyEditorContext(
            name="phased",
            filename="phased.yaml",
            file_path="/policies/phased.yaml",
            last_modified="2024-01-15T10:00:00Z",
            schema_version=12,
            track_order=[],
            audio_language_preference=[],
            subtitle_language_preference=[],
            commentary_patterns=[],
            default_flags={},
            transcode=None,
            transcription=None,
            phases=[{"name": "normalize", "container": {"target": "mkv"}}],
            config={"on_error": "skip"},
        )

        result = context.to_dict()

        assert result["phases"] is not None
        assert len(result["phases"]) == 1
        assert result["config"] == {"on_error": "skip"}
        # phase_names convenience field is added
        assert result["phase_names"] == ["normalize"]

    def test_to_dict_with_unknown_fields_warning(self):
        """Serializes context with unknown fields for warning display."""
        context = PolicyEditorContext(
            name="test",
            filename="test.yaml",
            file_path="/policies/test.yaml",
            last_modified="2024-01-15T10:00:00Z",
            schema_version=12,
            track_order=[],
            audio_language_preference=[],
            subtitle_language_preference=[],
            commentary_patterns=[],
            default_flags={},
            transcode=None,
            transcription=None,
            unknown_fields=["custom_field", "another_unknown"],
        )

        result = context.to_dict()

        assert result["unknown_fields"] == ["custom_field", "another_unknown"]

    def test_to_dict_with_parse_error(self):
        """Serializes context with parse error."""
        context = PolicyEditorContext(
            name="broken",
            filename="broken.yaml",
            file_path="/policies/broken.yaml",
            last_modified="2024-01-15T10:00:00Z",
            schema_version=12,
            track_order=[],
            audio_language_preference=[],
            subtitle_language_preference=[],
            commentary_patterns=[],
            default_flags={},
            transcode=None,
            transcription=None,
            parse_error="Invalid YAML syntax at line 5",
        )

        result = context.to_dict()

        assert result["parse_error"] == "Invalid YAML syntax at line 5"
