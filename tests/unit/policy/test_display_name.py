"""Unit tests for policy display name (name field) support.

Tests for the optional 'name' field in policy YAML files that provides
a user-friendly display name for the GUI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vpo.policy.discovery import _parse_policy_file
from vpo.policy.editor import KNOWN_POLICY_FIELDS
from vpo.policy.loader import PolicyValidationError, load_policy_from_dict

# Minimal valid phased policy dict, used as a base for loader tests.
_BASE_POLICY = {
    "schema_version": 13,
    "config": {"on_error": "continue"},
    "phases": [{"name": "apply", "track_order": ["video"]}],
}

# Minimal valid policy YAML body (after the name line).
_YAML_BODY = (
    "config:\n"
    "  audio_languages: [eng]\n"
    "phases:\n"
    "  - name: apply\n"
    "    track_order: [video]\n"
)


def _load_with_name(name_value):
    """Load a policy dict with the given 'name' value merged in."""
    return load_policy_from_dict({**_BASE_POLICY, "name": name_value})


def _write_policy_yaml(tmp_path, *, name_line: str = "") -> Path:
    """Write a minimal policy YAML file, optionally with a name line."""
    policy_file = tmp_path / "test.yaml"
    header = "schema_version: 13\n"
    if name_line:
        header += name_line + "\n"
    policy_file.write_text(header + _YAML_BODY)
    return policy_file


class TestPolicySchemaNameField:
    """Tests for name field on PolicySchema dataclass."""

    def test_name_defaults_to_none(self):
        """PolicySchema name field defaults to None."""
        policy = load_policy_from_dict(_BASE_POLICY)
        assert policy.name is None

    def test_name_accepted_when_provided(self):
        """PolicySchema accepts a name field."""
        policy = _load_with_name("My Anime Policy")
        assert policy.name == "My Anime Policy"

    def test_name_with_description_and_category(self):
        """All metadata fields work together."""
        policy = load_policy_from_dict(
            {
                **_BASE_POLICY,
                "name": "Full Metadata",
                "description": "A test policy",
                "category": "organize",
            }
        )
        assert policy.name == "Full Metadata"
        assert policy.description == "A test policy"
        assert policy.category == "organize"


class TestPolicyModelNameValidation:
    """Tests for name field validation in PolicyModel (pydantic)."""

    def test_whitespace_stripped(self):
        """Name field has whitespace stripped."""
        policy = _load_with_name("  Padded Name  ")
        assert policy.name == "Padded Name"

    def test_empty_string_rejected(self):
        """Empty string name is rejected."""
        with pytest.raises(PolicyValidationError, match="name"):
            _load_with_name("")

    def test_whitespace_only_rejected(self):
        """Whitespace-only name is rejected."""
        with pytest.raises(PolicyValidationError, match="name"):
            _load_with_name("   ")

    def test_name_at_max_length_accepted(self):
        """Name at exactly 200 chars is accepted."""
        name = "A" * 200
        policy = _load_with_name(name)
        assert policy.name == name

    def test_name_over_max_length_rejected(self):
        """Name over 200 chars is rejected."""
        with pytest.raises(PolicyValidationError):
            _load_with_name("A" * 201)

    def test_null_name_accepted(self):
        """Null (None) name is accepted."""
        policy = _load_with_name(None)
        assert policy.name is None


class TestDiscoveryDisplayName:
    """Tests for display_name extraction in _parse_policy_file."""

    def test_display_name_extracted(self, tmp_path):
        """Display name extracted from YAML 'name' field."""
        policy_file = _write_policy_yaml(tmp_path, name_line="name: My Cool Policy")
        result = _parse_policy_file(policy_file)
        assert result.display_name == "My Cool Policy"
        assert result.name == "test"  # filename stem unchanged

    def test_display_name_none_when_absent(self, tmp_path):
        """Display name is None when not in YAML."""
        policy_file = _write_policy_yaml(tmp_path)
        result = _parse_policy_file(policy_file)
        assert result.display_name is None

    def test_display_name_strips_whitespace(self, tmp_path):
        """Display name with whitespace is stripped."""
        policy_file = _write_policy_yaml(tmp_path, name_line="name: '  Padded  '")
        result = _parse_policy_file(policy_file)
        assert result.display_name == "Padded"

    def test_display_name_empty_string_becomes_none(self, tmp_path):
        """Empty string display name becomes None."""
        policy_file = _write_policy_yaml(tmp_path, name_line="name: ''")
        result = _parse_policy_file(policy_file)
        assert result.display_name is None

    def test_display_name_non_string_ignored(self, tmp_path):
        """Non-string display name is ignored."""
        policy_file = _write_policy_yaml(tmp_path, name_line="name: 42")
        result = _parse_policy_file(policy_file)
        assert result.display_name is None

    def test_display_name_in_to_dict(self, tmp_path):
        """Display name appears in to_dict output."""
        policy_file = _write_policy_yaml(tmp_path, name_line="name: My Policy")
        result = _parse_policy_file(policy_file)
        d = result.to_dict()
        assert d["display_name"] == "My Policy"


class TestKnownPolicyFieldsIncludesName:
    """Tests that KNOWN_POLICY_FIELDS includes 'name'."""

    def test_name_in_known_fields(self):
        """KNOWN_POLICY_FIELDS includes 'name' for display name."""
        assert "name" in KNOWN_POLICY_FIELDS


class TestRoundTripEditorPreservesName:
    """Tests that the round-trip editor preserves the name field."""

    def test_name_preserved_on_load_save(self, tmp_path):
        """Name field is preserved through load/save cycle."""
        from vpo.policy.editor import PolicyRoundTripEditor

        policy_file = tmp_path / "test.yaml"
        policy_file.write_text(
            "schema_version: 13\n"
            "name: My Policy\n"
            "config:\n"
            "  audio_languages:\n"
            "    - eng\n"
            "phases:\n"
            "  - name: apply\n"
            "    track_order:\n"
            "      - video\n"
        )

        editor = PolicyRoundTripEditor(policy_file, allowed_dir=tmp_path)
        data = editor.load()
        assert data["name"] == "My Policy"

        # Save with a modification
        data["name"] = "Updated Policy"
        editor.save(data)

        # Reload and verify
        data2 = editor.load()
        assert data2["name"] == "Updated Policy"
