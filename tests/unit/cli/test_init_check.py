"""Unit tests for CLI initialization check."""

import os
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from vpo.cli import main


class TestInitializationCheck:
    """Tests for _check_initialization function."""

    @pytest.fixture
    def runner(self):
        """Create a Click test runner."""
        return CliRunner()

    @pytest.fixture
    def temp_data_dir(self, tmp_path):
        """Create a temporary data directory."""
        data_dir = tmp_path / ".vpo"
        return data_dir

    def test_already_initialized_continues(self, runner, temp_data_dir):
        """Test that initialized VPO continues normally."""
        # Create config.toml to simulate initialized state
        temp_data_dir.mkdir(parents=True)
        (temp_data_dir / "config.toml").write_text("[logging]\nlevel = 'info'\n")

        with patch.dict(os.environ, {"VPO_DATA_DIR": str(temp_data_dir)}):
            # Run doctor command (simple command that should work)
            result = runner.invoke(main, ["doctor"])

        # Should not show initialization prompt
        assert "VPO is not initialized" not in result.output

    def test_init_command_skips_check(self, runner, temp_data_dir):
        """Test that init command skips initialization check."""
        # Don't create config.toml - not initialized
        with patch.dict(os.environ, {"VPO_DATA_DIR": str(temp_data_dir)}):
            result = runner.invoke(main, ["init", "--dry-run"])

        # Should not prompt for initialization
        assert "VPO is not initialized. Would you like to initialize now?" not in (
            result.output
        )
        # Should show dry-run output
        assert "Would create" in result.output or "No changes made" in result.output

    def test_not_initialized_non_interactive_exits(self, runner, temp_data_dir):
        """Test that non-interactive mode exits with error."""
        # Don't create config.toml - not initialized
        # sys.stdin.isatty() returns False by default in test environment
        with patch.dict(os.environ, {"VPO_DATA_DIR": str(temp_data_dir)}):
            result = runner.invoke(main, ["doctor"])

        assert result.exit_code == 1
        # Error message should be present (may be in stderr which gets mixed in)
        assert "VPO is not initialized" in result.output
        assert "vpo init" in result.output

    def test_not_initialized_interactive_user_declines(self, runner, temp_data_dir):
        """Test that declining initialization exits with message."""
        # Mock _is_interactive to return True for interactive mode
        with (
            patch.dict(os.environ, {"VPO_DATA_DIR": str(temp_data_dir)}),
            patch("vpo.cli._is_interactive", return_value=True),
        ):
            # Simulate user typing 'n' to decline
            result = runner.invoke(main, ["doctor"], input="n\n")

        assert result.exit_code == 1
        assert "VPO requires initialization before use" in result.output

    def test_not_initialized_interactive_user_accepts(self, runner, temp_data_dir):
        """Test that accepting initialization runs init and continues."""
        # Mock _is_interactive to return True for interactive mode
        with (
            patch.dict(os.environ, {"VPO_DATA_DIR": str(temp_data_dir)}),
            patch("vpo.cli._is_interactive", return_value=True),
        ):
            # Simulate user typing 'y' to accept
            result = runner.invoke(main, ["doctor"], input="y\n")

        # Should show init output (either success or created files)
        assert (
            "VPO initialized successfully" in result.output
            or "Created" in result.output
        )
        # Should continue with the command
        assert "Continuing with doctor" in result.output


class TestInitializationCheckEdgeCases:
    """Edge case tests for initialization check."""

    @pytest.fixture
    def runner(self):
        """Create a Click test runner."""
        return CliRunner()

    @pytest.fixture
    def temp_data_dir(self, tmp_path):
        """Create a temporary data directory."""
        data_dir = tmp_path / ".vpo"
        return data_dir

    def test_tool_detection_failure_handled_gracefully(self, runner, temp_data_dir):
        """Test that tool detection failures during interactive init don't crash."""
        with (
            patch.dict(os.environ, {"VPO_DATA_DIR": str(temp_data_dir)}),
            patch("vpo.cli._is_interactive", return_value=True),
            patch(
                "vpo.cli.init.get_tool_registry",
                side_effect=OSError("Mock cache error"),
            ),
        ):
            # Simulate user typing 'y' to accept
            result = runner.invoke(main, ["doctor"], input="y\n")

        # Should still succeed despite tool detection cache error
        # (falls back to detect_all_tools)
        assert result.exit_code == 0 or "Continuing with doctor" in result.output
        # Should show init output
        assert (
            "VPO initialized successfully" in result.output
            or "Created" in result.output
        )

    def test_version_flag_works_without_init(self, runner):
        """Test that --version works without initialization."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "video-policy-orchestrator" in result.output.lower() or "version" in (
            result.output.lower()
        )

    def test_help_flag_works_without_init(self, runner):
        """Test that --help works without initialization."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Video Policy Orchestrator" in result.output
