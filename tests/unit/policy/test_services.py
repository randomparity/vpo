"""Tests for policy service functions."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vpo.policy.discovery import clear_policy_cache
from vpo.policy.services import get_default_policy_path, list_policies


class TestGetDefaultPolicyPath:
    """Tests for get_default_policy_path function.

    Note: The vpo.config.profiles module may not exist in the codebase yet.
    The get_default_policy_path function is designed to gracefully handle
    ImportError when the profiles module is missing. These tests verify
    that behavior as well as testing with mocked profiles when available.
    """

    def test_returns_path_from_profile(self):
        """get_default_policy_path returns path from active profile."""
        import sys
        from types import ModuleType

        # Create a mock profiles module with get_active_profile function
        mock_profiles_module = ModuleType("vpo.config.profiles")
        mock_profile = MagicMock()
        mock_profile.default_policy = Path("/home/user/.vpo/policies/default.yaml")
        mock_profiles_module.get_active_profile = MagicMock(return_value=mock_profile)

        with patch.dict(sys.modules, {"vpo.config.profiles": mock_profiles_module}):
            result = get_default_policy_path()

        assert result == Path("/home/user/.vpo/policies/default.yaml")

    def test_returns_none_when_no_profile(self):
        """get_default_policy_path returns None when no active profile."""
        import sys
        from types import ModuleType

        mock_profiles_module = ModuleType("vpo.config.profiles")
        mock_profiles_module.get_active_profile = MagicMock(return_value=None)

        with patch.dict(sys.modules, {"vpo.config.profiles": mock_profiles_module}):
            result = get_default_policy_path()

        assert result is None

    def test_returns_none_when_no_default_policy(self):
        """get_default_policy_path returns None when profile has no default."""
        import sys
        from types import ModuleType

        mock_profiles_module = ModuleType("vpo.config.profiles")
        mock_profile = MagicMock()
        mock_profile.default_policy = None
        mock_profiles_module.get_active_profile = MagicMock(return_value=mock_profile)

        with patch.dict(sys.modules, {"vpo.config.profiles": mock_profiles_module}):
            result = get_default_policy_path()

        assert result is None

    def test_returns_none_on_import_error(self):
        """get_default_policy_path returns None on ImportError."""
        # When the profiles module doesn't exist, the function returns None
        # This is the actual behavior in the codebase
        result = get_default_policy_path()

        # The function should return None on import error
        assert result is None

    def test_returns_none_on_attribute_error(self):
        """get_default_policy_path returns None on AttributeError."""
        import sys
        from types import ModuleType

        # Create a mock profiles module but profile lacks default_policy
        mock_profiles_module = ModuleType("vpo.config.profiles")
        mock_profile = MagicMock(spec=[])  # Empty spec = no attributes
        mock_profiles_module.get_active_profile = MagicMock(return_value=mock_profile)

        with patch.dict(sys.modules, {"vpo.config.profiles": mock_profiles_module}):
            result = get_default_policy_path()

        # profile.default_policy raises AttributeError, function returns None
        assert result is None


class TestListPolicies:
    """Tests for list_policies function."""

    def setup_method(self):
        """Clear policy cache before each test."""
        clear_policy_cache()

    def test_returns_policy_list_response(self, tmp_path: Path):
        """list_policies returns PolicyListResponse."""
        policy_file = tmp_path / "test.yaml"
        policy_file.write_text("schema_version: 13\nphases:\n  - name: test")

        with patch("vpo.policy.services.get_default_policy_path", return_value=None):
            result = list_policies(tmp_path)

        assert result.total == 1
        assert len(result.policies) == 1
        assert result.policies[0].name == "test"
        assert result.directory_exists is True

    def test_empty_directory(self, tmp_path: Path):
        """list_policies handles empty directory."""
        with patch("vpo.policy.services.get_default_policy_path", return_value=None):
            result = list_policies(tmp_path)

        assert result.total == 0
        assert result.policies == []
        assert result.directory_exists is True

    def test_nonexistent_directory(self, tmp_path: Path):
        """list_policies handles non-existent directory."""
        nonexistent = tmp_path / "does_not_exist"

        with patch("vpo.policy.services.get_default_policy_path", return_value=None):
            result = list_policies(nonexistent)

        assert result.total == 0
        assert result.policies == []
        assert result.directory_exists is False

    def test_marks_default_policy(self, tmp_path: Path):
        """list_policies marks default policy."""
        policy_file = tmp_path / "default.yaml"
        policy_file.write_text("schema_version: 13\nphases:\n  - name: test")

        with patch(
            "vpo.policy.services.get_default_policy_path", return_value=policy_file
        ):
            result = list_policies(tmp_path)

        assert result.policies[0].is_default is True
        assert result.default_policy_missing is False

    def test_multiple_policies_sorted(self, tmp_path: Path):
        """list_policies returns policies sorted alphabetically."""
        (tmp_path / "zebra.yaml").write_text(
            "schema_version: 13\nphases:\n  - name: test"
        )
        (tmp_path / "alpha.yaml").write_text(
            "schema_version: 13\nphases:\n  - name: test"
        )
        (tmp_path / "beta.yaml").write_text(
            "schema_version: 13\nphases:\n  - name: test"
        )

        with patch("vpo.policy.services.get_default_policy_path", return_value=None):
            result = list_policies(tmp_path)

        assert result.total == 3
        names = [p.name for p in result.policies]
        assert names == ["alpha", "beta", "zebra"]

    def test_default_policy_sorted_first(self, tmp_path: Path):
        """list_policies sorts default policy first."""
        (tmp_path / "zebra.yaml").write_text(
            "schema_version: 13\nphases:\n  - name: test"
        )
        default_file = tmp_path / "alpha.yaml"
        default_file.write_text("schema_version: 13\nphases:\n  - name: test")

        # Make zebra the default, should appear first despite name
        with patch(
            "vpo.policy.services.get_default_policy_path",
            return_value=tmp_path / "zebra.yaml",
        ):
            result = list_policies(tmp_path)

        assert result.policies[0].name == "zebra"
        assert result.policies[0].is_default is True

    def test_reports_missing_default(self, tmp_path: Path):
        """list_policies reports when configured default is missing."""
        (tmp_path / "test.yaml").write_text(
            "schema_version: 13\nphases:\n  - name: test"
        )

        # Configured default doesn't exist
        missing_default = tmp_path / "nonexistent.yaml"

        with patch(
            "vpo.policy.services.get_default_policy_path", return_value=missing_default
        ):
            result = list_policies(tmp_path)

        assert result.default_policy_missing is True

    def test_includes_policies_directory(self, tmp_path: Path):
        """list_policies includes policies_directory in response."""
        with patch("vpo.policy.services.get_default_policy_path", return_value=None):
            result = list_policies(tmp_path)

        assert result.policies_directory == str(tmp_path)

    def test_includes_default_policy_path(self, tmp_path: Path):
        """list_policies includes default_policy_path in response."""
        default_path = tmp_path / "default.yaml"

        with patch(
            "vpo.policy.services.get_default_policy_path", return_value=default_path
        ):
            result = list_policies(tmp_path)

        assert result.default_policy_path == str(default_path)

    def test_null_default_policy_path(self, tmp_path: Path):
        """list_policies handles None default_policy_path."""
        with patch("vpo.policy.services.get_default_policy_path", return_value=None):
            result = list_policies(tmp_path)

        assert result.default_policy_path is None
