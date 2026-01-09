"""Unit tests for profile loading and validation.

Tests for T037 (loading/validation) and T038 (merging precedence).
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from vpo.config.models import (
    BehaviorConfig,
    JobsConfig,
    LoggingConfig,
    Profile,
    VPOConfig,
)
from vpo.config.profiles import (
    ProfileError,
    ProfileNotFoundError,
    get_profiles_directory,
    list_profiles,
    load_profile,
    merge_profile_with_config,
    validate_profile,
)

# =============================================================================
# T037: Unit tests for profile loading and validation
# =============================================================================


class TestGetProfilesDirectory:
    """Tests for get_profiles_directory()."""

    def test_returns_vpo_profiles_path(self) -> None:
        """Should return ~/.vpo/profiles/ path."""
        result = get_profiles_directory()
        assert result == Path.home() / ".vpo" / "profiles"


class TestListProfiles:
    """Tests for list_profiles()."""

    def test_returns_empty_when_dir_not_exists(self, tmp_path: Path) -> None:
        """Should return empty list when profiles directory doesn't exist."""
        with patch("vpo.config.profiles.get_profiles_directory") as mock:
            mock.return_value = tmp_path / "nonexistent"
            result = list_profiles()
            assert result == []

    def test_returns_profile_names(self, tmp_path: Path) -> None:
        """Should return profile names without .yaml extension."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "movies.yaml").write_text("name: movies")
        (profiles_dir / "tv.yaml").write_text("name: tv")
        (profiles_dir / ".hidden.yaml").write_text("name: hidden")  # Should be ignored

        with patch("vpo.config.profiles.get_profiles_directory") as mock:
            mock.return_value = profiles_dir
            result = list_profiles()
            assert sorted(result) == ["movies", "tv"]

    def test_ignores_non_yaml_files(self, tmp_path: Path) -> None:
        """Should ignore non-yaml files."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "movies.yaml").write_text("name: movies")
        (profiles_dir / "readme.txt").write_text("readme")
        (profiles_dir / "data.json").write_text("{}")

        with patch("vpo.config.profiles.get_profiles_directory") as mock:
            mock.return_value = profiles_dir
            result = list_profiles()
            assert result == ["movies"]


class TestLoadProfile:
    """Tests for load_profile()."""

    def test_load_minimal_profile(self, tmp_path: Path) -> None:
        """Should load a profile with just a name."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "minimal.yaml").write_text("name: minimal")

        with patch("vpo.config.profiles.get_profiles_directory") as mock:
            mock.return_value = profiles_dir
            profile = load_profile("minimal")

            assert profile.name == "minimal"
            assert profile.description is None
            assert profile.default_policy is None

    def test_load_full_profile(self, tmp_path: Path) -> None:
        """Should load a profile with all sections."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        profile_yaml = """
name: movies
description: Movie settings
default_policy: ~/policies/movies.yaml

behavior:
  warn_on_missing_features: false
  show_upgrade_suggestions: true

logging:
  level: debug
  file: ~/.vpo/logs/movies.log
  format: json

jobs:
  retention_days: 14
  auto_purge: false
"""
        (profiles_dir / "movies.yaml").write_text(profile_yaml)

        with patch("vpo.config.profiles.get_profiles_directory") as mock:
            mock.return_value = profiles_dir
            profile = load_profile("movies")

            assert profile.name == "movies"
            assert profile.description == "Movie settings"
            assert profile.default_policy == Path.home() / "policies" / "movies.yaml"

            assert profile.behavior is not None
            assert profile.behavior.warn_on_missing_features is False
            assert profile.behavior.show_upgrade_suggestions is True

            assert profile.logging is not None
            assert profile.logging.level == "debug"
            assert profile.logging.file == Path.home() / ".vpo" / "logs" / "movies.log"
            assert profile.logging.format == "json"

            assert profile.jobs is not None
            assert profile.jobs.retention_days == 14
            assert profile.jobs.auto_purge is False

    def test_profile_not_found(self, tmp_path: Path) -> None:
        """Should raise ProfileNotFoundError for missing profile."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        with patch("vpo.config.profiles.get_profiles_directory") as mock:
            mock.return_value = profiles_dir
            with pytest.raises(ProfileNotFoundError) as exc_info:
                load_profile("nonexistent")
            assert "Profile not found: nonexistent" in str(exc_info.value)

    def test_invalid_profile_name(self) -> None:
        """Should reject invalid profile names."""
        with pytest.raises(ProfileError) as exc_info:
            load_profile("invalid name")  # Space not allowed
        assert "alphanumeric" in str(exc_info.value)

        with pytest.raises(ProfileError) as exc_info:
            load_profile("invalid/path")  # Slash not allowed
        assert "alphanumeric" in str(exc_info.value)

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        """Should raise ProfileError for invalid YAML."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "bad.yaml").write_text("invalid: yaml: content:")

        with patch("vpo.config.profiles.get_profiles_directory") as mock:
            mock.return_value = profiles_dir
            with pytest.raises(ProfileError) as exc_info:
                load_profile("bad")
            assert "Invalid YAML" in str(exc_info.value)

    def test_name_from_filename_if_not_in_yaml(self, tmp_path: Path) -> None:
        """Should use filename as name if not specified in YAML."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "myprofile.yaml").write_text("description: A profile")

        with patch("vpo.config.profiles.get_profiles_directory") as mock:
            mock.return_value = profiles_dir
            profile = load_profile("myprofile")
            assert profile.name == "myprofile"


class TestValidateProfile:
    """Tests for validate_profile()."""

    def test_valid_profile(self, tmp_path: Path) -> None:
        """Should return no errors for valid profile."""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text("policy: content")

        profile = Profile(
            name="test",
            description="Test profile",
            default_policy=policy_file,
        )

        errors = validate_profile(profile)
        assert errors == []

    def test_missing_policy_file(self, tmp_path: Path) -> None:
        """Should report error for missing policy file."""
        profile = Profile(
            name="test",
            default_policy=tmp_path / "nonexistent.yaml",
        )

        errors = validate_profile(profile)
        assert len(errors) == 1
        assert "Policy file not found" in errors[0]

    def test_missing_log_directory(self, tmp_path: Path) -> None:
        """Should report error for missing log directory."""
        profile = Profile(
            name="test",
            logging=LoggingConfig(
                file=tmp_path / "nonexistent" / "app.log",
            ),
        )

        errors = validate_profile(profile)
        assert len(errors) == 1
        assert "Log directory does not exist" in errors[0]

    def test_multiple_errors(self, tmp_path: Path) -> None:
        """Should report all validation errors."""
        profile = Profile(
            name="test",
            default_policy=tmp_path / "missing-policy.yaml",
            logging=LoggingConfig(
                file=tmp_path / "missing-dir" / "app.log",
            ),
        )

        errors = validate_profile(profile)
        assert len(errors) == 2


# =============================================================================
# T038: Unit tests for profile merging precedence
# =============================================================================


class TestMergeProfileWithConfig:
    """Tests for merge_profile_with_config()."""

    def test_profile_overrides_config(self) -> None:
        """Profile settings should override base config."""
        base_config = VPOConfig()
        base_config.behavior.warn_on_missing_features = True
        base_config.logging.level = "info"

        profile = Profile(
            name="test",
            behavior=BehaviorConfig(
                warn_on_missing_features=False,
                show_upgrade_suggestions=True,
            ),
            logging=LoggingConfig(
                level="debug",
                format="json",
            ),
        )

        merged = merge_profile_with_config(profile, base_config)

        # Profile values should override
        assert merged.behavior.warn_on_missing_features is False
        assert merged.logging.level == "debug"
        assert merged.logging.format == "json"

    def test_config_preserved_when_profile_section_missing(self) -> None:
        """Base config should be preserved when profile doesn't override."""
        base_config = VPOConfig()
        base_config.behavior.warn_on_missing_features = True
        base_config.jobs.retention_days = 30

        profile = Profile(
            name="test",
            logging=LoggingConfig(level="debug"),
            # behavior and jobs not specified
        )

        merged = merge_profile_with_config(profile, base_config)

        # Original values preserved where profile doesn't override
        assert merged.behavior.warn_on_missing_features is True
        assert merged.jobs.retention_days == 30
        # Profile value applied
        assert merged.logging.level == "debug"

    def test_original_config_not_modified(self) -> None:
        """Original config should not be mutated."""
        base_config = VPOConfig()
        base_config.logging.level = "info"

        profile = Profile(
            name="test",
            logging=LoggingConfig(level="debug"),
        )

        merged = merge_profile_with_config(profile, base_config)

        # Original unchanged
        assert base_config.logging.level == "info"
        # Merged has new value
        assert merged.logging.level == "debug"

    def test_empty_profile_returns_copy(self) -> None:
        """Profile with no overrides should return config copy."""
        base_config = VPOConfig()
        base_config.logging.level = "warning"

        profile = Profile(name="empty")

        merged = merge_profile_with_config(profile, base_config)

        # Should be a copy with same values
        assert merged.logging.level == "warning"
        assert merged is not base_config

    def test_jobs_config_override(self) -> None:
        """Should properly override jobs config."""
        base_config = VPOConfig()
        base_config.jobs.retention_days = 30
        base_config.jobs.auto_purge = True

        profile = Profile(
            name="test",
            jobs=JobsConfig(
                retention_days=7,
                auto_purge=False,
            ),
        )

        merged = merge_profile_with_config(profile, base_config)

        assert merged.jobs.retention_days == 7
        assert merged.jobs.auto_purge is False
