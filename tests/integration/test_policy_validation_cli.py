"""Integration tests for the vpo policy validate command."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from vpo.cli import main
from vpo.cli.exit_codes import ExitCode


class TestPolicyValidateHelp:
    """Tests for vpo policy validate --help."""

    def test_policy_group_help(self) -> None:
        """Test that policy group shows help."""
        runner = CliRunner()
        result = runner.invoke(main, ["policy", "--help"])

        assert result.exit_code == 0
        assert "Manage policy files" in result.output
        assert "validate" in result.output

    def test_policy_validate_help(self) -> None:
        """Test that policy validate command shows help."""
        runner = CliRunner()
        result = runner.invoke(main, ["policy", "validate", "--help"])

        assert result.exit_code == 0
        assert "Validate a policy YAML file" in result.output
        assert "--json" in result.output
        assert "POLICY_FILE" in result.output


class TestPolicyValidateErrors:
    """Tests for error cases in policy validation."""

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Test validate with non-existent file."""
        runner = CliRunner()
        nonexistent = tmp_path / "nonexistent.yaml"
        result = runner.invoke(main, ["policy", "validate", str(nonexistent)])

        assert result.exit_code == ExitCode.POLICY_VALIDATION_ERROR
        assert "Invalid" in result.output
        assert "File not found" in result.output

    def test_file_not_found_json(self, tmp_path: Path) -> None:
        """Test validate with non-existent file and JSON output."""
        runner = CliRunner()
        nonexistent = tmp_path / "nonexistent.yaml"
        result = runner.invoke(main, ["policy", "validate", str(nonexistent), "--json"])

        assert result.exit_code == ExitCode.POLICY_VALIDATION_ERROR
        data = json.loads(result.output)
        assert data["valid"] is False
        assert "file_not_found" in data["errors"][0]["code"]

    def test_invalid_yaml_syntax(self, tmp_path: Path) -> None:
        """Test validate with invalid YAML syntax."""
        runner = CliRunner()
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("invalid: [\n")  # Unclosed bracket

        result = runner.invoke(main, ["policy", "validate", str(bad_yaml)])

        assert result.exit_code == ExitCode.POLICY_VALIDATION_ERROR
        assert "Invalid" in result.output

    def test_invalid_yaml_syntax_json(self, tmp_path: Path) -> None:
        """Test validate with invalid YAML syntax and JSON output."""
        runner = CliRunner()
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("invalid: [\n")

        result = runner.invoke(main, ["policy", "validate", str(bad_yaml), "--json"])

        assert result.exit_code == ExitCode.POLICY_VALIDATION_ERROR
        data = json.loads(result.output)
        assert data["valid"] is False
        assert len(data["errors"]) > 0

    def test_empty_file(self, tmp_path: Path) -> None:
        """Test validate with empty file."""
        runner = CliRunner()
        empty = tmp_path / "empty.yaml"
        empty.write_text("")

        result = runner.invoke(main, ["policy", "validate", str(empty)])

        assert result.exit_code == ExitCode.POLICY_VALIDATION_ERROR
        assert "Invalid" in result.output

    def test_non_mapping_yaml(self, tmp_path: Path) -> None:
        """Test validate with non-mapping YAML (e.g., a list)."""
        runner = CliRunner()
        list_yaml = tmp_path / "list.yaml"
        list_yaml.write_text("- item1\n- item2\n")

        result = runner.invoke(main, ["policy", "validate", str(list_yaml)])

        assert result.exit_code == ExitCode.POLICY_VALIDATION_ERROR
        assert "Invalid" in result.output

    def test_wrong_schema_version(self, tmp_path: Path) -> None:
        """Test validate with wrong schema version."""
        runner = CliRunner()
        old_schema = tmp_path / "old.yaml"
        old_schema.write_text(
            "schema_version: 11\n"
            "phases:\n"
            "  - name: test\n"
            "    container:\n"
            "      target: mkv\n"
        )

        result = runner.invoke(main, ["policy", "validate", str(old_schema)])

        assert result.exit_code == ExitCode.POLICY_VALIDATION_ERROR
        assert "Invalid" in result.output
        assert "schema_version 12" in result.output.lower() or "12" in result.output

    def test_missing_phases_key(self, tmp_path: Path) -> None:
        """Test validate with missing phases key."""
        runner = CliRunner()
        no_phases = tmp_path / "no_phases.yaml"
        no_phases.write_text("schema_version: 12\nconfig:\n  on_error: skip\n")

        result = runner.invoke(main, ["policy", "validate", str(no_phases)])

        assert result.exit_code == ExitCode.POLICY_VALIDATION_ERROR
        assert "Invalid" in result.output
        assert "phases" in result.output.lower()


class TestPolicyValidateSuccess:
    """Tests for successful policy validation."""

    def test_valid_minimal_policy(self, tmp_path: Path) -> None:
        """Test validate with a minimal valid policy."""
        runner = CliRunner()
        valid = tmp_path / "valid.yaml"
        valid.write_text(
            "schema_version: 12\n"
            "phases:\n"
            "  - name: test\n"
            "    container:\n"
            "      target: mkv\n"
        )

        result = runner.invoke(main, ["policy", "validate", str(valid)])

        assert result.exit_code == 0
        assert "Valid" in result.output

    def test_valid_policy_json(self, tmp_path: Path) -> None:
        """Test validate with valid policy and JSON output."""
        runner = CliRunner()
        valid = tmp_path / "valid.yaml"
        valid.write_text(
            "schema_version: 12\n"
            "phases:\n"
            "  - name: test\n"
            "    container:\n"
            "      target: mkv\n"
        )

        result = runner.invoke(main, ["policy", "validate", str(valid), "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["valid"] is True
        assert data["file"] == str(valid)
        assert len(data["errors"]) == 0


@pytest.mark.integration
class TestExamplePolicies:
    """Tests that all example policies are valid."""

    @pytest.fixture
    def examples_dir(self) -> Path:
        """Get the examples/policies directory."""
        # Find the examples directory relative to the test file
        test_dir = Path(__file__).parent
        repo_root = test_dir.parent.parent
        return repo_root / "examples" / "policies"

    def test_examples_dir_exists(self, examples_dir: Path) -> None:
        """Verify the examples directory exists."""
        assert examples_dir.exists(), f"Examples directory not found: {examples_dir}"

    def test_all_example_policies_valid(self, examples_dir: Path) -> None:
        """Validate all example policies."""
        runner = CliRunner()
        policies = list(examples_dir.glob("*.yaml"))

        assert len(policies) > 0, "No example policies found"

        failures = []
        for policy_file in policies:
            result = runner.invoke(main, ["policy", "validate", str(policy_file)])
            if result.exit_code != 0:
                failures.append((policy_file.name, result.output))

        if failures:
            msg = "The following example policies failed validation:\n"
            for name, output in failures:
                msg += f"\n{name}:\n{output}\n"
            pytest.fail(msg)

    @pytest.mark.parametrize(
        "policy_name",
        [
            "audio-synthesis.yaml",
            "conditional-rules.yaml",
            "container-conversion.yaml",
            "media-normalization.yaml",
            "multi-phase-production.yaml",
            "selective-phases.yaml",
            "single-phase-minimal.yaml",
            "track-filtering.yaml",
            "transcode-conditional.yaml",
            "transcode-hevc.yaml",
            "transcription-analysis.yaml",
            "two-phase-workflow.yaml",
        ],
    )
    def test_individual_example_policy(
        self, examples_dir: Path, policy_name: str
    ) -> None:
        """Validate each example policy individually."""
        runner = CliRunner()
        policy_file = examples_dir / policy_name

        if not policy_file.exists():
            pytest.skip(f"Policy file not found: {policy_name}")

        result = runner.invoke(main, ["policy", "validate", str(policy_file)])

        assert result.exit_code == 0, (
            f"Policy {policy_name} validation failed:\n{result.output}"
        )
