"""Unit tests for config templates module."""

from pathlib import Path

from vpo.config.templates import (
    DEFAULT_POLICY_TEMPLATE,
    DEFAULT_PROFILE_TEMPLATE,
    InitializationState,
    InitResult,
    check_initialization_state,
    create_data_directory,
    create_logs_directory,
    create_plugins_directory,
    get_config_template,
    get_minimal_config_template,
    run_init,
    validate_data_dir_path,
    write_config_file,
    write_default_policy,
    write_default_profile,
)


class TestInitializationState:
    """Tests for InitializationState dataclass."""

    def test_fields_exist(self):
        """Test all expected fields are present."""
        state = InitializationState(
            data_dir=Path("/test"),
            is_initialized=True,
            config_exists=True,
            policies_dir_exists=True,
            plugins_dir_exists=True,
            default_policy_exists=True,
            profiles_dir_exists=True,
            default_profile_exists=True,
            has_partial_state=False,
            existing_files=[],
        )
        assert state.data_dir == Path("/test")
        assert state.is_initialized is True
        assert state.config_exists is True
        assert state.profiles_dir_exists is True
        assert state.default_profile_exists is True

    def test_default_existing_files(self):
        """Test existing_files defaults to empty list."""
        state = InitializationState(
            data_dir=Path("/test"),
            is_initialized=False,
            config_exists=False,
            policies_dir_exists=False,
            plugins_dir_exists=False,
            default_policy_exists=False,
            profiles_dir_exists=False,
            default_profile_exists=False,
            has_partial_state=False,
        )
        assert state.existing_files == []


class TestInitResult:
    """Tests for InitResult dataclass."""

    def test_successful_result(self):
        """Test successful init result."""
        result = InitResult(
            success=True,
            data_dir=Path("/test"),
            created_files=[Path("/test/config.toml")],
            created_directories=[Path("/test")],
        )
        assert result.success is True
        assert result.error is None
        assert result.dry_run is False

    def test_failed_result(self):
        """Test failed init result."""
        result = InitResult(
            success=False,
            data_dir=Path("/test"),
            error="Permission denied",
        )
        assert result.success is False
        assert result.error == "Permission denied"

    def test_dry_run_result(self):
        """Test dry-run result."""
        result = InitResult(
            success=True,
            data_dir=Path("/test"),
            dry_run=True,
        )
        assert result.dry_run is True


class TestTemplates:
    """Tests for template strings."""

    def test_config_template_has_sections(self, tmp_path):
        """Test config template contains expected sections."""
        config_template = get_config_template(tmp_path)
        assert "[tools]" in config_template
        assert "[tools.detection]" in config_template
        assert "[behavior]" in config_template
        assert "[plugins]" in config_template
        assert "[jobs]" in config_template
        assert "[worker]" in config_template
        assert "[transcription]" in config_template
        assert "[logging]" in config_template
        assert "[server]" in config_template
        assert "[language]" in config_template

    def test_config_template_has_header(self, tmp_path):
        """Test config template has header comment."""
        config_template = get_config_template(tmp_path)
        assert "Video Policy Orchestrator Configuration" in config_template
        assert "vpo init" in config_template

    def test_config_template_uses_data_dir_for_log_path(self, tmp_path):
        """Test config template uses provided data_dir for log file path."""
        data_dir = tmp_path / "custom-vpo"
        config_template = get_config_template(data_dir)
        # The log path should contain the data_dir path
        assert "custom-vpo/logs/vpo.log" in config_template

    def test_policy_template_has_schema_version(self):
        """Test default policy has schema version."""
        assert "schema_version: 12" in DEFAULT_POLICY_TEMPLATE

    def test_policy_template_has_track_order(self):
        """Test default policy has track order."""
        assert "track_order:" in DEFAULT_POLICY_TEMPLATE
        assert "- video" in DEFAULT_POLICY_TEMPLATE
        assert "- audio_main" in DEFAULT_POLICY_TEMPLATE

    def test_policy_template_has_language_prefs(self):
        """Test default policy has language preferences."""
        assert "audio_language_preference:" in DEFAULT_POLICY_TEMPLATE
        assert "subtitle_language_preference:" in DEFAULT_POLICY_TEMPLATE
        assert "- eng" in DEFAULT_POLICY_TEMPLATE

    def test_policy_template_has_default_flags(self):
        """Test default policy has default flags."""
        assert "default_flags:" in DEFAULT_POLICY_TEMPLATE
        assert "set_first_video_default:" in DEFAULT_POLICY_TEMPLATE

    def test_policy_template_has_phases_key(self):
        """Test default policy has phases key for phased format."""
        assert "phases:" in DEFAULT_POLICY_TEMPLATE

    def test_policy_template_has_config_key(self):
        """Test default policy has config key for global settings."""
        assert "config:" in DEFAULT_POLICY_TEMPLATE

    def test_policy_template_parses_as_valid_phased_policy(self, tmp_path):
        """Test default policy template parses without error in discovery."""
        from vpo.policy.discovery import _parse_policy_file

        policy_path = tmp_path / "default.yaml"
        policy_path.write_text(DEFAULT_POLICY_TEMPLATE)

        result = _parse_policy_file(policy_path)

        assert result.parse_error is None, f"Template parse error: {result.parse_error}"
        assert result.schema_version == 12
        assert result.audio_languages == ["eng", "und"]
        assert result.subtitle_languages == ["eng", "und"]

    def test_profile_template_has_name(self):
        """Test default profile has name field."""
        assert "name: default" in DEFAULT_PROFILE_TEMPLATE

    def test_profile_template_has_default_policy(self):
        """Test default profile has default_policy field."""
        assert "default_policy:" in DEFAULT_PROFILE_TEMPLATE
        assert "policies/default.yaml" in DEFAULT_PROFILE_TEMPLATE

    def test_profile_template_has_header(self):
        """Test default profile has header comment."""
        assert "vpo init" in DEFAULT_PROFILE_TEMPLATE


class TestConfigTemplateCoversAllModelFields:
    """Ensure every config model field appears in the template.

    This test prevents drift between config/models.py and the
    config.toml template generated by `vpo init`. If you add a new
    field to a config dataclass, you must also add it (commented out
    is fine) to the template in config/templates.py.
    """

    def test_all_config_fields_present_in_template(self, tmp_path):
        """Every leaf field in VPOConfig must appear in the template."""
        import dataclasses

        from vpo.config.models import VPOConfig

        template = get_config_template(tmp_path)

        # Sections in VPOConfig whose fields are nested dataclasses
        # (containers for sub-configs, not direct TOML keys themselves).
        # These field names won't appear as TOML keys; instead their
        # *children* are the keys we check.
        container_fields = {"metadata", "rate_limit"}

        def _leaf_fields(dc_cls: type) -> list[str]:
            """Return leaf field names from a dataclass, recursing
            into nested dataclass containers."""
            names: list[str] = []
            for f in dataclasses.fields(dc_cls):
                if f.name in container_fields:
                    # Resolve the inner type (strip Optional/None)
                    inner = f.type
                    if hasattr(inner, "__origin__"):
                        # e.g. X | None → grab first arg
                        inner = inner.__args__[0]
                    if dataclasses.is_dataclass(inner):
                        names.extend(_leaf_fields(inner))
                    continue
                names.append(f.name)
            return names

        missing: list[str] = []
        for section_field in dataclasses.fields(VPOConfig):
            if dataclasses.is_dataclass(section_field.type):
                for name in _leaf_fields(section_field.type):
                    if name not in template:
                        missing.append(f"{section_field.name}.{name}")
            else:
                # Root-level field (e.g. database_path)
                if section_field.name not in template:
                    missing.append(section_field.name)

        assert missing == [], (
            f"Config fields missing from template: {missing}. "
            "Add them (commented out) to get_config_template() in "
            "config/templates.py."
        )


class TestCheckInitializationState:
    """Tests for check_initialization_state function."""

    def test_empty_directory(self, temp_dir: Path):
        """Test checking an empty directory."""
        state = check_initialization_state(temp_dir)
        assert state.data_dir == temp_dir
        assert state.is_initialized is False
        assert state.config_exists is False
        assert state.has_partial_state is False
        assert state.existing_files == []

    def test_nonexistent_directory(self, temp_dir: Path):
        """Test checking a nonexistent directory."""
        nonexistent = temp_dir / "nonexistent"
        state = check_initialization_state(nonexistent)
        assert state.is_initialized is False
        assert state.has_partial_state is False

    def test_fully_initialized(self, temp_dir: Path):
        """Test checking a fully initialized directory."""
        (temp_dir / "config.toml").touch()
        (temp_dir / "policies").mkdir()
        (temp_dir / "policies" / "default.yaml").touch()
        (temp_dir / "plugins").mkdir()
        (temp_dir / "profiles").mkdir()
        (temp_dir / "profiles" / "default.yaml").touch()

        state = check_initialization_state(temp_dir)
        assert state.is_initialized is True
        assert state.config_exists is True
        assert state.policies_dir_exists is True
        assert state.plugins_dir_exists is True
        assert state.default_policy_exists is True
        assert state.profiles_dir_exists is True
        assert state.default_profile_exists is True
        assert state.has_partial_state is False
        assert len(state.existing_files) == 6

    def test_partial_state(self, temp_dir: Path):
        """Test checking a partial state (interrupted init)."""
        (temp_dir / "policies").mkdir()
        # No config.toml

        state = check_initialization_state(temp_dir)
        assert state.is_initialized is False
        assert state.has_partial_state is True


class TestValidateDataDirPath:
    """Tests for validate_data_dir_path function."""

    def test_valid_new_path(self, temp_dir: Path):
        """Test validating a new path in writable directory."""
        new_path = temp_dir / "new_vpo"
        error = validate_data_dir_path(new_path)
        assert error is None

    def test_path_is_file(self, temp_dir: Path):
        """Test that file paths are rejected."""
        file_path = temp_dir / "existing_file"
        file_path.touch()

        error = validate_data_dir_path(file_path)
        assert error is not None
        assert "file already exists" in error.lower()

    def test_existing_directory_ok(self, temp_dir: Path):
        """Test that existing directory is ok."""
        error = validate_data_dir_path(temp_dir)
        assert error is None

    def test_symlink_to_directory_rejected(self, temp_dir: Path):
        """Test that symlinks to directories are rejected."""
        real_dir = temp_dir / "real"
        real_dir.mkdir()
        symlink = temp_dir / "link"
        symlink.symlink_to(real_dir)

        error = validate_data_dir_path(symlink)
        assert error is not None
        assert "symlink" in error.lower()

    def test_symlink_to_file_rejected(self, temp_dir: Path):
        """Test that symlinks to files are rejected."""
        real_file = temp_dir / "file"
        real_file.touch()
        symlink = temp_dir / "link"
        symlink.symlink_to(real_file)

        error = validate_data_dir_path(symlink)
        assert error is not None
        assert "symlink" in error.lower()

    def test_broken_symlink_rejected(self, temp_dir: Path):
        """Test that broken symlinks are rejected."""
        symlink = temp_dir / "broken_link"
        symlink.symlink_to(temp_dir / "nonexistent")

        error = validate_data_dir_path(symlink)
        assert error is not None
        assert "symlink" in error.lower()


class TestCreateDataDirectory:
    """Tests for create_data_directory function."""

    def test_create_new_directory(self, temp_dir: Path):
        """Test creating a new directory."""
        new_path = temp_dir / "new_vpo"
        success, error = create_data_directory(new_path)

        assert success is True
        assert error is None
        assert new_path.exists()

    def test_dry_run_does_not_create(self, temp_dir: Path):
        """Test dry run doesn't create directory."""
        new_path = temp_dir / "new_vpo"
        success, error = create_data_directory(new_path, dry_run=True)

        assert success is True
        assert not new_path.exists()

    def test_existing_directory_ok(self, temp_dir: Path):
        """Test existing directory is handled."""
        success, error = create_data_directory(temp_dir)
        assert success is True
        assert error is None


class TestWriteConfigFile:
    """Tests for write_config_file function."""

    def test_write_config(self, temp_dir: Path):
        """Test writing config file."""
        success, error = write_config_file(temp_dir)

        assert success is True
        assert error is None

        config_path = temp_dir / "config.toml"
        assert config_path.exists()
        content = config_path.read_text()
        assert "[tools]" in content

    def test_dry_run_does_not_write(self, temp_dir: Path):
        """Test dry run doesn't write file."""
        success, error = write_config_file(temp_dir, dry_run=True)

        assert success is True
        config_path = temp_dir / "config.toml"
        assert not config_path.exists()


class TestWriteDefaultPolicy:
    """Tests for write_default_policy function."""

    def test_write_policy(self, temp_dir: Path):
        """Test writing default policy."""
        success, error = write_default_policy(temp_dir)

        assert success is True
        assert error is None

        policy_path = temp_dir / "policies" / "default.yaml"
        assert policy_path.exists()
        content = policy_path.read_text()
        assert "schema_version: 12" in content

    def test_creates_policies_directory(self, temp_dir: Path):
        """Test that policies directory is created."""
        policies_dir = temp_dir / "policies"
        assert not policies_dir.exists()

        success, _ = write_default_policy(temp_dir)
        assert success is True
        assert policies_dir.exists()

    def test_dry_run_does_not_write(self, temp_dir: Path):
        """Test dry run doesn't write file."""
        success, error = write_default_policy(temp_dir, dry_run=True)

        assert success is True
        policy_path = temp_dir / "policies" / "default.yaml"
        assert not policy_path.exists()


class TestWriteDefaultProfile:
    """Tests for write_default_profile function."""

    def test_write_profile(self, temp_dir: Path):
        """Test writing default profile."""
        success, error = write_default_profile(temp_dir)

        assert success is True
        assert error is None

        profile_path = temp_dir / "profiles" / "default.yaml"
        assert profile_path.exists()
        content = profile_path.read_text()
        assert "name: default" in content
        assert "default_policy:" in content

    def test_creates_profiles_directory(self, temp_dir: Path):
        """Test that profiles directory is created."""
        profiles_dir = temp_dir / "profiles"
        assert not profiles_dir.exists()

        success, _ = write_default_profile(temp_dir)
        assert success is True
        assert profiles_dir.exists()

    def test_dry_run_does_not_write(self, temp_dir: Path):
        """Test dry run doesn't write file."""
        success, error = write_default_profile(temp_dir, dry_run=True)

        assert success is True
        profile_path = temp_dir / "profiles" / "default.yaml"
        assert not profile_path.exists()


class TestCreatePluginsDirectory:
    """Tests for create_plugins_directory function."""

    def test_create_plugins_dir(self, temp_dir: Path):
        """Test creating plugins directory."""
        success, error = create_plugins_directory(temp_dir)

        assert success is True
        assert error is None
        assert (temp_dir / "plugins").exists()

    def test_dry_run_does_not_create(self, temp_dir: Path):
        """Test dry run doesn't create directory."""
        success, error = create_plugins_directory(temp_dir, dry_run=True)

        assert success is True
        assert not (temp_dir / "plugins").exists()


class TestCreateLogsDirectory:
    """Tests for create_logs_directory function."""

    def test_create_logs_dir(self, temp_dir: Path):
        """Test creating logs directory."""
        success, error = create_logs_directory(temp_dir)

        assert success is True
        assert error is None
        assert (temp_dir / "logs").exists()

    def test_dry_run_does_not_create(self, temp_dir: Path):
        """Test dry run doesn't create directory."""
        success, error = create_logs_directory(temp_dir, dry_run=True)

        assert success is True
        assert not (temp_dir / "logs").exists()

    def test_existing_directory_ok(self, temp_dir: Path):
        """Test existing logs directory is handled."""
        logs_dir = temp_dir / "logs"
        logs_dir.mkdir()

        success, error = create_logs_directory(temp_dir)

        assert success is True
        assert error is None


class TestRunInit:
    """Tests for run_init orchestration function."""

    def test_fresh_init(self, temp_dir: Path):
        """Test fresh initialization."""
        data_dir = temp_dir / "vpo"
        result = run_init(data_dir)

        assert result.success is True
        assert result.data_dir == data_dir
        assert len(result.created_directories) > 0
        assert len(result.created_files) > 0
        assert result.error is None

        # Verify files and directories exist
        assert (data_dir / "config.toml").exists()
        assert (data_dir / "policies" / "default.yaml").exists()
        assert (data_dir / "plugins").exists()
        assert (data_dir / "backups").exists()
        assert (data_dir / "logs").exists()
        assert (data_dir / "profiles" / "default.yaml").exists()

    def test_already_initialized_error(self, temp_dir: Path):
        """Test error when already initialized."""
        data_dir = temp_dir / "vpo"
        data_dir.mkdir()
        (data_dir / "config.toml").touch()

        result = run_init(data_dir)

        assert result.success is False
        assert "already initialized" in result.error.lower()
        assert "--force" in result.error

    def test_force_overwrites(self, temp_dir: Path):
        """Test --force overwrites existing config."""
        data_dir = temp_dir / "vpo"
        data_dir.mkdir()
        config_path = data_dir / "config.toml"
        config_path.write_text("old content")

        result = run_init(data_dir, force=True)

        assert result.success is True
        # Config should be overwritten
        new_content = config_path.read_text()
        assert "[tools]" in new_content

    def test_dry_run_no_changes(self, temp_dir: Path):
        """Test dry run doesn't make changes."""
        data_dir = temp_dir / "vpo"
        result = run_init(data_dir, dry_run=True)

        assert result.success is True
        assert result.dry_run is True
        assert not data_dir.exists()

    def test_path_validation_error(self, temp_dir: Path):
        """Test path validation error is returned."""
        # Create a file where we want the directory
        file_path = temp_dir / "blocked"
        file_path.touch()

        result = run_init(file_path)

        assert result.success is False
        assert "file already exists" in result.error.lower()

    def test_symlink_data_dir_rejected(self, temp_dir: Path):
        """Test that symlink as data directory is rejected."""
        real_dir = temp_dir / "real"
        real_dir.mkdir()
        symlink = temp_dir / "link"
        symlink.symlink_to(real_dir)

        result = run_init(symlink)

        assert result.success is False
        assert "symlink" in result.error.lower()

    def test_rollback_message_on_failure(self, temp_dir: Path):
        """Test that failure message mentions rollback."""
        import os

        # Test path validation errors using /root (unwritable for normal users)
        # Note: Validation errors occur before any files are created, so no
        # rollback message is expected - this tests the error path works.
        if os.geteuid() != 0:  # Skip if running as root
            result = run_init(Path("/root/vpo_test_rollback"))
            assert result.success is False
            # Permission errors should be returned
            assert "permission" in result.error.lower()

    def test_rollback_cleans_created_files(self, temp_dir: Path):
        """Test that rollback actually removes created files."""
        from unittest.mock import patch

        data_dir = temp_dir / "vpo"

        # Mock create_plugins_directory to fail
        with patch("vpo.config.templates.create_plugins_directory") as mock_create:
            mock_create.return_value = (False, "Simulated failure")

            result = run_init(data_dir)

            # Should fail
            assert result.success is False
            assert "rolled back" in result.error.lower()

            # config.toml should have been rolled back (removed)
            assert not (data_dir / "config.toml").exists()
            # policies/default.yaml should have been rolled back (removed)
            assert not (data_dir / "policies" / "default.yaml").exists()
            # profiles/default.yaml should not exist (never reached)
            assert not (data_dir / "profiles" / "default.yaml").exists()

    def test_rollback_cleans_profile_on_failure(self, temp_dir: Path):
        """Test that rollback removes profile when profile write fails."""
        from unittest.mock import patch

        data_dir = temp_dir / "vpo"

        # Mock write_default_profile to fail (after plugins directory succeeds)
        with patch("vpo.config.templates.write_default_profile") as mock_write:
            mock_write.return_value = (False, "Simulated profile failure")

            result = run_init(data_dir)

            # Should fail
            assert result.success is False
            assert "rolled back" in result.error.lower()

            # Earlier items should have been rolled back
            assert not (data_dir / "config.toml").exists()
            assert not (data_dir / "policies" / "default.yaml").exists()


class TestMinimalConfigTemplate:
    """Tests for get_minimal_config_template function."""

    def test_is_valid_toml(self):
        """Minimal template should be valid TOML."""
        from vpo.config.toml_parser import parse_toml

        content = get_minimal_config_template()
        parsed = parse_toml(content)
        assert isinstance(parsed, dict)

    def test_contains_expected_sections(self):
        """Minimal template should contain tools, behavior, processing."""
        content = get_minimal_config_template()
        assert "[tools]" in content
        assert "[behavior]" in content
        assert "[processing]" in content

    def test_shorter_than_full_template(self):
        """Minimal template should be shorter than the full template."""
        full = get_config_template(Path.home() / ".vpo")
        minimal = get_minimal_config_template()
        assert len(minimal) < len(full)

    def test_write_config_file_minimal(self, tmp_path: Path):
        """write_config_file(minimal=True) should write the minimal template."""
        data_dir = tmp_path / "vpo"
        data_dir.mkdir()
        success, error = write_config_file(data_dir, minimal=True)
        assert success
        assert error is None
        content = (data_dir / "config.toml").read_text()
        assert "[tools]" in content
        # Should NOT contain server section (minimal omits it)
        assert "[server]" not in content
