"""Unit tests for policy display name (name field) support.

Tests for the optional 'name' field in policy YAML files that provides
a user-friendly display name for the GUI.
"""

from __future__ import annotations

import pytest

from vpo.policy.discovery import _parse_policy_file
from vpo.policy.editor import KNOWN_POLICY_FIELDS
from vpo.policy.loader import PolicyValidationError, load_policy_from_dict


class TestPolicySchemaNameField:
    """Tests for name field on PolicySchema dataclass."""

    def test_name_defaults_to_none(self):
        """PolicySchema name field defaults to None."""
        policy = load_policy_from_dict(
            {
                "schema_version": 12,
                "config": {"on_error": "continue"},
                "phases": [{"name": "apply", "track_order": ["video"]}],
            }
        )
        assert policy.name is None

    def test_name_accepted_when_provided(self):
        """PolicySchema accepts a name field."""
        policy = load_policy_from_dict(
            {
                "schema_version": 12,
                "name": "My Anime Policy",
                "config": {"on_error": "continue"},
                "phases": [{"name": "apply", "track_order": ["video"]}],
            }
        )
        assert policy.name == "My Anime Policy"

    def test_name_with_description_and_category(self):
        """All metadata fields work together."""
        policy = load_policy_from_dict(
            {
                "schema_version": 12,
                "name": "Full Metadata",
                "description": "A test policy",
                "category": "organize",
                "config": {"on_error": "continue"},
                "phases": [{"name": "apply", "track_order": ["video"]}],
            }
        )
        assert policy.name == "Full Metadata"
        assert policy.description == "A test policy"
        assert policy.category == "organize"


class TestPolicyModelNameValidation:
    """Tests for name field validation in PolicyModel (pydantic)."""

    def test_whitespace_stripped(self):
        """Name field has whitespace stripped."""
        policy = load_policy_from_dict(
            {
                "schema_version": 12,
                "name": "  Padded Name  ",
                "config": {"on_error": "continue"},
                "phases": [{"name": "apply", "track_order": ["video"]}],
            }
        )
        assert policy.name == "Padded Name"

    def test_empty_string_rejected(self):
        """Empty string name is rejected."""
        with pytest.raises(PolicyValidationError, match="name"):
            load_policy_from_dict(
                {
                    "schema_version": 12,
                    "name": "",
                    "config": {"on_error": "continue"},
                    "phases": [{"name": "apply", "track_order": ["video"]}],
                }
            )

    def test_whitespace_only_rejected(self):
        """Whitespace-only name is rejected."""
        with pytest.raises(PolicyValidationError, match="name"):
            load_policy_from_dict(
                {
                    "schema_version": 12,
                    "name": "   ",
                    "config": {"on_error": "continue"},
                    "phases": [{"name": "apply", "track_order": ["video"]}],
                }
            )

    def test_null_name_accepted(self):
        """Null (None) name is accepted."""
        policy = load_policy_from_dict(
            {
                "schema_version": 12,
                "name": None,
                "config": {"on_error": "continue"},
                "phases": [{"name": "apply", "track_order": ["video"]}],
            }
        )
        assert policy.name is None


class TestDiscoveryDisplayName:
    """Tests for display_name extraction in _parse_policy_file."""

    def test_display_name_extracted(self, tmp_path):
        """Display name extracted from YAML 'name' field."""
        policy_file = tmp_path / "test.yaml"
        policy_file.write_text(
            "schema_version: 12\n"
            "name: My Cool Policy\n"
            "config:\n"
            "  audio_language_preference: [eng]\n"
            "phases:\n"
            "  - name: apply\n"
            "    track_order: [video]\n"
        )
        result = _parse_policy_file(policy_file)
        assert result.display_name == "My Cool Policy"
        assert result.name == "test"  # filename stem unchanged

    def test_display_name_none_when_absent(self, tmp_path):
        """Display name is None when not in YAML."""
        policy_file = tmp_path / "test.yaml"
        policy_file.write_text(
            "schema_version: 12\n"
            "config:\n"
            "  audio_language_preference: [eng]\n"
            "phases:\n"
            "  - name: apply\n"
            "    track_order: [video]\n"
        )
        result = _parse_policy_file(policy_file)
        assert result.display_name is None

    def test_display_name_strips_whitespace(self, tmp_path):
        """Display name with whitespace is stripped."""
        policy_file = tmp_path / "test.yaml"
        policy_file.write_text(
            "schema_version: 12\n"
            "name: '  Padded  '\n"
            "config:\n"
            "  audio_language_preference: [eng]\n"
            "phases:\n"
            "  - name: apply\n"
            "    track_order: [video]\n"
        )
        result = _parse_policy_file(policy_file)
        assert result.display_name == "Padded"

    def test_display_name_empty_string_becomes_none(self, tmp_path):
        """Empty string display name becomes None."""
        policy_file = tmp_path / "test.yaml"
        policy_file.write_text(
            "schema_version: 12\n"
            "name: ''\n"
            "config:\n"
            "  audio_language_preference: [eng]\n"
            "phases:\n"
            "  - name: apply\n"
            "    track_order: [video]\n"
        )
        result = _parse_policy_file(policy_file)
        assert result.display_name is None

    def test_display_name_non_string_ignored(self, tmp_path):
        """Non-string display name is ignored."""
        policy_file = tmp_path / "test.yaml"
        policy_file.write_text(
            "schema_version: 12\n"
            "name: 42\n"
            "config:\n"
            "  audio_language_preference: [eng]\n"
            "phases:\n"
            "  - name: apply\n"
            "    track_order: [video]\n"
        )
        result = _parse_policy_file(policy_file)
        assert result.display_name is None

    def test_display_name_in_to_dict(self, tmp_path):
        """Display name appears in to_dict output."""
        policy_file = tmp_path / "test.yaml"
        policy_file.write_text(
            "schema_version: 12\n"
            "name: My Policy\n"
            "config:\n"
            "  audio_language_preference: [eng]\n"
            "phases:\n"
            "  - name: apply\n"
            "    track_order: [video]\n"
        )
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
            "schema_version: 12\n"
            "name: My Policy\n"
            "config:\n"
            "  audio_language_preference:\n"
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
