"""Unit tests for init CLI command."""

import os
from pathlib import Path
from unittest import mock

from click.testing import CliRunner

from vpo.cli.init import (
    _display_error,
    _display_result,
    _get_data_dir,
    init_command,
)
from vpo.config.templates import InitResult


class TestGetDataDir:
    """Tests for _get_data_dir function."""

    def test_cli_option_takes_precedence(self):
        """Test that CLI option takes precedence over env var."""
        cli_path = Path("/cli/path")
        with mock.patch.dict(os.environ, {"VPO_DATA_DIR": "/env/path"}):
            result = _get_data_dir(cli_path)
            assert result == cli_path

    def test_env_var_used_when_no_cli(self):
        """Test that env var is used when no CLI option."""
        with mock.patch.dict(os.environ, {"VPO_DATA_DIR": "/env/path"}):
            result = _get_data_dir(None)
            assert result == Path("/env/path")

    def test_default_when_no_cli_or_env(self):
        """Test default path when no CLI option or env var."""
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("VPO_DATA_DIR", None)
            result = _get_data_dir(None)
            assert result == Path.home() / ".vpo"

    def test_env_var_expands_tilde(self):
        """Test that tilde is expanded in env var."""
        with mock.patch.dict(os.environ, {"VPO_DATA_DIR": "~/custom/vpo"}):
            result = _get_data_dir(None)
            assert result == Path.home() / "custom" / "vpo"


class TestDisplayResult:
    """Tests for _display_result function (output format)."""

    def test_dry_run_output(self, capsys):
        """Test dry run output format."""
        result = InitResult(
            success=True,
            data_dir=Path("/test"),
            created_directories=[Path("/test"), Path("/test/policies")],
            created_files=[Path("/test/config.toml")],
            dry_run=True,
        )
        _display_result(result, force=False)
        captured = capsys.readouterr()

        assert "Would create /test/" in captured.out
        assert "Would create /test/config.toml" in captured.out
        assert "No changes made (dry run)." in captured.out

    def test_success_output(self, capsys):
        """Test successful init output format."""
        result = InitResult(
            success=True,
            data_dir=Path("/test"),
            created_directories=[Path("/test")],
            created_files=[Path("/test/config.toml")],
        )
        _display_result(result, force=False)
        captured = capsys.readouterr()

        assert "Created /test/" in captured.out
        assert "VPO initialized successfully!" in captured.out
        assert "Next steps:" in captured.out

    def test_force_output(self, capsys):
        """Test force reinit output format."""
        result = InitResult(
            success=True,
            data_dir=Path("/test"),
            created_files=[Path("/test/config.toml")],
            skipped_files=[Path("/test/config.toml")],
        )
        _display_result(result, force=True)
        captured = capsys.readouterr()

        assert "Warning: Overwriting" in captured.err
        assert "Replaced /test/config.toml" in captured.out
        assert "VPO re-initialized with defaults." in captured.out


class TestDisplayError:
    """Tests for _display_error function."""

    def test_already_initialized_error(self, capsys):
        """Test already initialized error message."""
        result = InitResult(
            success=False,
            data_dir=Path("/test"),
            error="VPO is already initialized at /test",
            skipped_files=[Path("/test/config.toml")],
        )
        _display_error(result)
        captured = capsys.readouterr()

        assert "already initialized" in captured.err.lower()
        assert "Existing files:" in captured.out
        assert "Use --force" in captured.out


class TestInitCommand:
    """Tests for init_command Click command."""

    def test_help_output(self):
        """Test help message."""
        runner = CliRunner()
        result = runner.invoke(init_command, ["--help"])

        assert result.exit_code == 0
        assert "--data-dir" in result.output
        assert "--force" in result.output
        assert "--dry-run" in result.output
        assert "--quiet" in result.output

    def test_dry_run(self, temp_dir: Path):
        """Test dry run doesn't create files."""
        runner = CliRunner()
        target = temp_dir / "vpo"

        result = runner.invoke(init_command, ["--data-dir", str(target), "--dry-run"])

        assert result.exit_code == 0
        assert "Would create" in result.output
        assert "No changes made" in result.output
        assert not target.exists()

    def test_fresh_init(self, temp_dir: Path):
        """Test fresh initialization."""
        runner = CliRunner()
        target = temp_dir / "vpo"

        result = runner.invoke(init_command, ["--data-dir", str(target)])

        assert result.exit_code == 0
        assert "initialized successfully" in result.output
        assert target.exists()
        assert (target / "config.toml").exists()

    def test_already_initialized_error(self, temp_dir: Path):
        """Test error when already initialized."""
        runner = CliRunner()
        target = temp_dir / "vpo"
        target.mkdir()
        (target / "config.toml").touch()

        result = runner.invoke(init_command, ["--data-dir", str(target)])

        assert result.exit_code == 1
        assert "already initialized" in result.output.lower()

    def test_force_overwrites(self, temp_dir: Path):
        """Test --force flag."""
        runner = CliRunner()
        target = temp_dir / "vpo"
        target.mkdir()
        config_path = target / "config.toml"
        config_path.write_text("old")

        result = runner.invoke(init_command, ["--data-dir", str(target), "--force"])

        assert result.exit_code == 0
        assert "re-initialized" in result.output
        # Verify config was overwritten
        assert "[tools]" in config_path.read_text()

    def test_env_var_respected(self, temp_dir: Path):
        """Test VPO_DATA_DIR environment variable."""
        runner = CliRunner()
        target = temp_dir / "env_vpo"

        result = runner.invoke(
            init_command,
            ["--dry-run"],
            env={"VPO_DATA_DIR": str(target)},
        )

        assert result.exit_code == 0
        assert str(target) in result.output

    def test_permission_error(self, temp_dir: Path):
        """Test permission error handling."""
        runner = CliRunner()
        # Try to create in root (should fail without sudo)
        result = runner.invoke(init_command, ["--data-dir", "/root/vpo-test"])

        assert result.exit_code == 1
        assert "permission denied" in result.output.lower()

    def test_path_is_file_error(self, temp_dir: Path):
        """Test error when path is a file."""
        runner = CliRunner()
        file_path = temp_dir / "file"
        file_path.touch()

        result = runner.invoke(init_command, ["--data-dir", str(file_path)])

        assert result.exit_code == 1
        assert "file already exists" in result.output.lower()

    def test_quiet_suppresses_output(self, temp_dir: Path):
        """Test --quiet flag suppresses output on success."""
        runner = CliRunner()
        target = temp_dir / "vpo"

        result = runner.invoke(init_command, ["--data-dir", str(target), "--quiet"])

        assert result.exit_code == 0
        # In quiet mode, no "VPO initialized successfully" message
        # Note: Log messages may still appear in test output, but the actual CLI
        # output from click.echo() should be suppressed
        assert "VPO initialized successfully" not in result.output
        assert "Next steps:" not in result.output
        assert target.exists()  # But init still works

    def test_quiet_shows_errors(self, temp_dir: Path):
        """Test --quiet flag still shows errors."""
        runner = CliRunner()
        target = temp_dir / "vpo"
        target.mkdir()
        (target / "config.toml").touch()

        result = runner.invoke(init_command, ["--data-dir", str(target), "--quiet"])

        assert result.exit_code == 1
        # Errors should still be shown even in quiet mode
        assert "already initialized" in result.output.lower()

    def test_symlink_data_dir_rejected(self, temp_dir: Path):
        """Test that symlinks are rejected as data directory."""
        runner = CliRunner()
        real_dir = temp_dir / "real"
        real_dir.mkdir()
        symlink = temp_dir / "link"
        symlink.symlink_to(real_dir)

        result = runner.invoke(init_command, ["--data-dir", str(symlink)])

        assert result.exit_code == 1
        assert "symlink" in result.output.lower()
