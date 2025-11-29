"""Integration tests for init command."""

from pathlib import Path

from click.testing import CliRunner

from video_policy_orchestrator.cli import main


class TestInitCommand:
    """Integration tests for vpo init command."""

    def test_init_help(self):
        """Test that init --help works."""
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--help"])
        assert result.exit_code == 0
        assert "Initialize VPO configuration directory" in result.output
        assert "--data-dir" in result.output
        assert "--force" in result.output
        assert "--dry-run" in result.output

    def test_init_fresh_directory(self, temp_dir: Path):
        """Test initializing a fresh directory."""
        runner = CliRunner()
        target = temp_dir / "vpo_test"

        result = runner.invoke(main, ["init", "--data-dir", str(target)])

        assert result.exit_code == 0
        assert "initialized successfully" in result.output

        # Verify created structure
        assert target.exists()
        assert (target / "config.toml").exists()
        assert (target / "policies").exists()
        assert (target / "policies" / "default.yaml").exists()
        assert (target / "plugins").exists()

    def test_init_dry_run(self, temp_dir: Path):
        """Test --dry-run shows what would be created."""
        runner = CliRunner()
        target = temp_dir / "vpo_test"

        result = runner.invoke(main, ["init", "--data-dir", str(target), "--dry-run"])

        assert result.exit_code == 0
        assert "Would create" in result.output
        assert "No changes made (dry run)" in result.output
        assert not target.exists()

    def test_init_already_initialized(self, temp_dir: Path):
        """Test error when already initialized."""
        runner = CliRunner()
        target = temp_dir / "vpo_test"

        # First init
        runner.invoke(main, ["init", "--data-dir", str(target)])

        # Second init should fail
        result = runner.invoke(main, ["init", "--data-dir", str(target)])

        assert result.exit_code == 1
        assert "already initialized" in result.output.lower()
        assert "--force" in result.output

    def test_init_force_overwrites(self, temp_dir: Path):
        """Test --force overwrites existing configuration."""
        runner = CliRunner()
        target = temp_dir / "vpo_test"

        # First init
        runner.invoke(main, ["init", "--data-dir", str(target)])

        # Modify config
        config_path = target / "config.toml"
        config_path.write_text("# Custom content\n")

        # Force reinit
        result = runner.invoke(main, ["init", "--data-dir", str(target), "--force"])

        assert result.exit_code == 0
        assert "re-initialized" in result.output

        # Verify config was overwritten
        content = config_path.read_text()
        assert "[tools]" in content  # Should have standard content

    def test_config_file_valid_toml(self, temp_dir: Path):
        """Test that generated config.toml is valid TOML."""
        runner = CliRunner()
        target = temp_dir / "vpo_test"

        runner.invoke(main, ["init", "--data-dir", str(target)])

        config_path = target / "config.toml"
        content = config_path.read_text()

        # Try to parse it
        try:
            import tomllib

            tomllib.loads(content)
        except ImportError:
            import tomli

            tomli.loads(content)
        # If we get here, it's valid TOML

    def test_policy_file_valid_yaml(self, temp_dir: Path):
        """Test that generated default.yaml is valid YAML."""
        import yaml

        runner = CliRunner()
        target = temp_dir / "vpo_test"

        runner.invoke(main, ["init", "--data-dir", str(target)])

        policy_path = target / "policies" / "default.yaml"
        content = policy_path.read_text()

        # Parse and verify structure
        data = yaml.safe_load(content)
        assert data["schema_version"] == 1
        assert "track_order" in data
        assert "audio_language_preference" in data

    def test_next_steps_shown(self, temp_dir: Path):
        """Test that next steps are displayed."""
        runner = CliRunner()
        target = temp_dir / "vpo_test"

        result = runner.invoke(main, ["init", "--data-dir", str(target)])

        assert result.exit_code == 0
        assert "Next steps:" in result.output
        # vpo doctor was removed from next steps - now shows config review and scan
        assert "config.toml" in result.output
        assert "vpo scan" in result.output

    def test_permission_error_message(self):
        """Test that permission errors are handled gracefully."""
        runner = CliRunner()

        result = runner.invoke(main, ["init", "--data-dir", "/root/vpo_test"])

        assert result.exit_code == 1
        assert "permission denied" in result.output.lower()

    def test_path_is_file_error(self, temp_dir: Path):
        """Test error when target is an existing file."""
        runner = CliRunner()
        file_path = temp_dir / "not_a_directory"
        file_path.touch()

        result = runner.invoke(main, ["init", "--data-dir", str(file_path)])

        assert result.exit_code == 1
        assert "file already exists" in result.output.lower()

    def test_env_var_fallback(self, temp_dir: Path):
        """Test VPO_DATA_DIR environment variable is used."""
        runner = CliRunner()
        target = temp_dir / "env_target"

        result = runner.invoke(
            main,
            ["init", "--dry-run"],
            env={"VPO_DATA_DIR": str(target)},
        )

        assert result.exit_code == 0
        assert str(target) in result.output

    def test_cli_option_overrides_env(self, temp_dir: Path):
        """Test --data-dir overrides VPO_DATA_DIR."""
        runner = CliRunner()
        env_target = temp_dir / "env_target"
        cli_target = temp_dir / "cli_target"

        result = runner.invoke(
            main,
            ["init", "--data-dir", str(cli_target), "--dry-run"],
            env={"VPO_DATA_DIR": str(env_target)},
        )

        assert result.exit_code == 0
        assert str(cli_target) in result.output

    def test_partial_state_recovery(self, temp_dir: Path):
        """Test initialization with partial state (interrupted init)."""
        runner = CliRunner()
        target = temp_dir / "vpo_test"

        # Create partial state (policies dir but no config)
        target.mkdir()
        (target / "policies").mkdir()

        # Init should complete the setup
        result = runner.invoke(main, ["init", "--data-dir", str(target)])

        assert result.exit_code == 0
        assert (target / "config.toml").exists()
        assert (target / "policies" / "default.yaml").exists()
        assert (target / "plugins").exists()

    def test_doctor_after_init(self, temp_dir: Path):
        """Test that vpo doctor passes after init."""
        runner = CliRunner()
        target = temp_dir / "vpo_test"

        # Initialize
        runner.invoke(main, ["init", "--data-dir", str(target)])

        # Doctor should work (may warn about missing tools, but shouldn't crash)
        result = runner.invoke(
            main,
            ["doctor"],
            env={"VPO_DATA_DIR": str(target)},
        )

        # Doctor command may return non-zero if tools are missing,
        # but it should not crash
        assert result.exception is None or isinstance(result.exception, SystemExit)
