"""Tests for vpo completion command."""

import pytest
from click.testing import CliRunner

from vpo.cli import main


class TestCompletionCommand:
    """Tests for shell completion generation."""

    @pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
    def test_completion_produces_output(self, runner: CliRunner, shell: str) -> None:
        """Test that completion command produces non-empty output for each shell."""
        result = runner.invoke(main, ["completion", shell])

        assert result.exit_code == 0
        assert len(result.output) > 0

    def test_completion_bash_contains_function(self, runner: CliRunner) -> None:
        """Test that bash completion contains the completion function."""
        result = runner.invoke(main, ["completion", "bash"])

        assert result.exit_code == 0
        assert "_vpo_completion" in result.output

    def test_completion_invalid_shell(self, runner: CliRunner) -> None:
        """Test that an invalid shell choice is rejected."""
        result = runner.invoke(main, ["completion", "powershell"])

        assert result.exit_code != 0

    def test_completion_help(self, runner: CliRunner) -> None:
        """Test that completion --help shows usage."""
        result = runner.invoke(main, ["completion", "--help"])

        assert result.exit_code == 0
        assert "bash" in result.output
        assert "zsh" in result.output
        assert "fish" in result.output
