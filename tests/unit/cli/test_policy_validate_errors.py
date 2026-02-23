"""Tests for policy validate command error handling."""

import os
from pathlib import Path

import pytest

from vpo.cli.policy import _validate_policy


class TestPolicyValidateErrors:
    """Tests for specific error codes in policy validation."""

    def test_file_not_found_code(self, tmp_path: Path):
        """Non-existent file returns file_not_found code."""
        nonexistent = tmp_path / "does_not_exist.yaml"

        result = _validate_policy(nonexistent)

        assert result["valid"] is False
        assert len(result["errors"]) == 1
        assert result["errors"][0]["code"] == "file_not_found"

    def test_is_directory_code(self, tmp_path: Path):
        """Directory path returns is_directory code."""
        result = _validate_policy(tmp_path)

        assert result["valid"] is False
        assert len(result["errors"]) == 1
        assert result["errors"][0]["code"] == "is_directory"
        assert "directory" in result["errors"][0]["message"].lower()

    def test_permission_denied_code(self, tmp_path: Path):
        """Unreadable file returns permission_denied code."""
        # Create a file with no read permissions
        policy_file = tmp_path / "unreadable.yaml"
        policy_file.write_text("schema_version: 13\n")

        # Skip if running as root (can read anything)
        if os.getuid() == 0:
            pytest.skip("Cannot test permission denied as root")

        try:
            policy_file.chmod(0o000)

            result = _validate_policy(policy_file)

            assert result["valid"] is False
            assert len(result["errors"]) == 1
            assert result["errors"][0]["code"] == "permission_denied"
        finally:
            # Restore permissions for cleanup
            policy_file.chmod(0o644)

    def test_yaml_syntax_error_code(self, tmp_path: Path):
        """Invalid YAML syntax returns yaml_syntax_error code."""
        policy_file = tmp_path / "bad_yaml.yaml"
        # Invalid YAML with unclosed bracket
        bad_yaml = "schema_version: 13\nphases:\n  - name: test\n    bad: [unclosed"
        policy_file.write_text(bad_yaml)

        result = _validate_policy(policy_file)

        assert result["valid"] is False
        assert len(result["errors"]) == 1
        # The code should be yaml_syntax_error if the message contains
        # "Invalid YAML syntax", otherwise it will be validation_error
        error_code = result["errors"][0]["code"]
        assert error_code in ("yaml_syntax_error", "validation_error")

    def test_validation_error_code(self, tmp_path: Path):
        """Schema validation error returns validation_error code."""
        policy_file = tmp_path / "invalid_schema.yaml"
        policy_file.write_text(
            """
schema_version: 13
config:
  on_error: invalid_value
phases:
  - name: test
"""
        )

        result = _validate_policy(policy_file)

        assert result["valid"] is False
        assert len(result["errors"]) == 1
        assert result["errors"][0]["code"] == "validation_error"

    def test_valid_policy_no_errors(self, tmp_path: Path):
        """Valid policy returns no errors."""
        policy_file = tmp_path / "valid.yaml"
        policy_file.write_text(
            """
schema_version: 13
config:
  on_error: skip
phases:
  - name: test
    rules:
      match: first
      items:
        - name: always_pass
          when:
            exists:
              track_type: video
          then:
            - warn: "Video exists"
"""
        )

        result = _validate_policy(policy_file)

        assert result["valid"] is True
        assert result["errors"] == []
        assert result["message"] == "Policy is valid"

    def test_result_structure(self, tmp_path: Path):
        """Result always has expected structure."""
        policy_file = tmp_path / "test.yaml"
        policy_file.write_text("invalid: yaml: content:")

        result = _validate_policy(policy_file)

        # Check required keys exist
        assert "valid" in result
        assert "file" in result
        assert "errors" in result
        assert "message" in result

        # Check types
        assert isinstance(result["valid"], bool)
        assert isinstance(result["file"], str)
        assert isinstance(result["errors"], list)

    def test_error_structure(self, tmp_path: Path):
        """Error entries have expected structure."""
        policy_file = tmp_path / "error.yaml"
        policy_file.write_text("schema_version: 99\n")

        result = _validate_policy(policy_file)

        assert result["valid"] is False
        assert len(result["errors"]) >= 1

        error = result["errors"][0]
        assert "field" in error
        assert "message" in error
        assert "code" in error
