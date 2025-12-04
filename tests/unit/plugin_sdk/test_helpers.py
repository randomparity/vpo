"""Unit tests for plugin_sdk helpers module."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from video_policy_orchestrator.plugin_sdk.helpers import (
    get_config,
    get_data_dir,
    get_host_identifier,
    get_logger,
    get_plugin_storage_dir,
    is_mkv_container,
    is_supported_container,
    normalize_path,
    normalize_path_for_matching,
)


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_logger_with_plugin_prefix(self) -> None:
        """Logger name should be 'plugin.<name>'."""
        logger = get_logger("my-plugin")
        assert logger.name == "plugin.my-plugin"

    def test_same_name_returns_same_logger(self) -> None:
        """Calling get_logger twice with same name returns same instance."""
        logger1 = get_logger("test-plugin")
        logger2 = get_logger("test-plugin")
        assert logger1 is logger2

    def test_returns_logger_instance(self) -> None:
        """Returns a logging.Logger instance."""
        logger = get_logger("sample")
        assert isinstance(logger, logging.Logger)


class TestGetConfig:
    """Tests for get_config function."""

    def test_returns_plugin_dirs_from_config(self) -> None:
        """get_config returns plugin_dirs from VPO config."""
        mock_config = MagicMock()
        mock_config.plugin_dirs = [Path("/plugins/a"), Path("/plugins/b")]
        mock_config.data_dir = Path("/data")

        with patch(
            "video_policy_orchestrator.config.loader.get_config",
            return_value=mock_config,
        ):
            result = get_config()
            assert result["plugin_dirs"] == ["/plugins/a", "/plugins/b"]

    def test_returns_data_dir_from_config(self) -> None:
        """get_config returns data_dir from VPO config."""
        mock_config = MagicMock()
        mock_config.plugin_dirs = []
        mock_config.data_dir = Path("/my/data")

        with patch(
            "video_policy_orchestrator.config.loader.get_config",
            return_value=mock_config,
        ):
            result = get_config()
            assert result["data_dir"] == "/my/data"

    def test_returns_fallback_on_config_load_error(self) -> None:
        """get_config returns empty dict on load error."""
        with patch(
            "video_policy_orchestrator.config.loader.get_config",
            side_effect=Exception("Config error"),
        ):
            result = get_config()
            assert result["plugin_dirs"] == []
            assert result["data_dir"] is None

    def test_plugin_dirs_converted_to_strings(self) -> None:
        """Plugin dirs are converted from Path to str."""
        mock_config = MagicMock()
        mock_config.plugin_dirs = [Path("/test")]
        mock_config.data_dir = None

        with patch(
            "video_policy_orchestrator.config.loader.get_config",
            return_value=mock_config,
        ):
            result = get_config()
            assert isinstance(result["plugin_dirs"][0], str)


class TestGetDataDir:
    """Tests for get_data_dir function."""

    def test_returns_configured_data_dir(self) -> None:
        """Returns data_dir from config if configured."""
        mock_config = MagicMock()
        mock_config.data_dir = Path("/custom/data")

        with patch(
            "video_policy_orchestrator.config.loader.get_config",
            return_value=mock_config,
        ):
            result = get_data_dir()
            assert result == Path("/custom/data")

    def test_returns_default_on_no_config(self) -> None:
        """Returns ~/.vpo/ when config has no data_dir."""
        mock_config = MagicMock()
        mock_config.data_dir = None

        with patch(
            "video_policy_orchestrator.config.loader.get_config",
            return_value=mock_config,
        ):
            result = get_data_dir()
            assert result == Path.home() / ".vpo"

    def test_returns_default_on_config_error(self) -> None:
        """Returns ~/.vpo/ when config loading fails."""
        with patch(
            "video_policy_orchestrator.config.loader.get_config",
            side_effect=Exception("Error"),
        ):
            result = get_data_dir()
            assert result == Path.home() / ".vpo"


class TestGetPluginStorageDir:
    """Tests for get_plugin_storage_dir function."""

    def test_returns_plugin_specific_subdir(self, tmp_path: Path) -> None:
        """Returns {data_dir}/plugins/{plugin_name}."""
        with patch(
            "video_policy_orchestrator.plugin_sdk.helpers.get_data_dir",
            return_value=tmp_path,
        ):
            result = get_plugin_storage_dir("my-plugin")
            assert result == tmp_path / "plugins" / "my-plugin"

    def test_creates_directory_if_not_exists(self, tmp_path: Path) -> None:
        """Creates storage directory and parents if needed."""
        with patch(
            "video_policy_orchestrator.plugin_sdk.helpers.get_data_dir",
            return_value=tmp_path,
        ):
            result = get_plugin_storage_dir("new-plugin")
            assert result.exists()
            assert result.is_dir()

    def test_handles_nested_plugin_names(self, tmp_path: Path) -> None:
        """Handles plugin names with hyphens."""
        with patch(
            "video_policy_orchestrator.plugin_sdk.helpers.get_data_dir",
            return_value=tmp_path,
        ):
            result = get_plugin_storage_dir("my-awesome-plugin")
            assert result.name == "my-awesome-plugin"
            assert result.exists()


class TestNormalizePath:
    """Tests for normalize_path function."""

    def test_expands_user_tilde(self) -> None:
        """Expands ~ to home directory."""
        result = normalize_path("~/test")
        assert "~" not in str(result)
        assert str(result).startswith(str(Path.home()))

    def test_resolves_to_absolute(self, tmp_path: Path) -> None:
        """Returns absolute path."""
        # Create a file to resolve to
        test_file = tmp_path / "test.txt"
        test_file.touch()

        result = normalize_path(str(test_file))
        assert result.is_absolute()

    def test_accepts_string_input(self) -> None:
        """Works with string input."""
        result = normalize_path("/test/path")
        assert isinstance(result, Path)

    def test_accepts_path_input(self) -> None:
        """Works with Path input."""
        result = normalize_path(Path("/test/path"))
        assert isinstance(result, Path)


class TestNormalizePathForMatching:
    """Tests for normalize_path_for_matching function."""

    def test_resolves_symlinks_when_exists(self, tmp_path: Path) -> None:
        """Resolves symlinks for existing paths."""
        # Create a real file and a symlink
        real_file = tmp_path / "real.mkv"
        real_file.touch()
        symlink = tmp_path / "link.mkv"
        symlink.symlink_to(real_file)

        result = normalize_path_for_matching(str(symlink))
        # Should resolve to the real file
        assert result == str(real_file)

    def test_uses_absolute_for_nonexistent(self) -> None:
        """Uses absolute() for non-existent paths."""
        result = normalize_path_for_matching("/nonexistent/path/file.mkv")
        assert result == "/nonexistent/path/file.mkv"

    def test_strips_trailing_slashes(self, tmp_path: Path) -> None:
        """Removes trailing slashes for consistency."""
        # Normalize path with trailing slash
        result = normalize_path_for_matching(str(tmp_path) + "/")
        assert not result.endswith("/")

    def test_returns_string(self, tmp_path: Path) -> None:
        """Returns string, not Path."""
        result = normalize_path_for_matching(str(tmp_path))
        assert isinstance(result, str)


class TestIsSupportedContainer:
    """Tests for is_supported_container function."""

    @pytest.mark.parametrize(
        "container",
        ["mkv", "matroska", "mp4", "m4v", "avi", "mov"],
    )
    def test_supported_formats(self, container: str) -> None:
        """mkv, matroska, mp4, m4v, avi, mov are supported."""
        assert is_supported_container(container) is True

    def test_case_insensitive(self) -> None:
        """Format check is case-insensitive."""
        assert is_supported_container("MKV") is True
        assert is_supported_container("Mp4") is True
        assert is_supported_container("AVI") is True

    @pytest.mark.parametrize(
        "container",
        ["wmv", "flv", "webm", "unknown", ""],
    )
    def test_unsupported_format(self, container: str) -> None:
        """Returns False for unknown formats."""
        assert is_supported_container(container) is False


class TestIsMkvContainer:
    """Tests for is_mkv_container function."""

    def test_mkv_recognized(self) -> None:
        """'mkv' returns True."""
        assert is_mkv_container("mkv") is True

    def test_matroska_recognized(self) -> None:
        """'matroska' returns True."""
        assert is_mkv_container("matroska") is True

    def test_mp4_not_mkv(self) -> None:
        """'mp4' returns False."""
        assert is_mkv_container("mp4") is False

    def test_case_insensitive(self) -> None:
        """Check is case-insensitive."""
        assert is_mkv_container("MKV") is True
        assert is_mkv_container("Matroska") is True
        assert is_mkv_container("MATROSKA") is True


class TestGetHostIdentifier:
    """Tests for get_host_identifier function."""

    def test_returns_hostname(self) -> None:
        """Returns socket.gethostname() result."""
        with patch("socket.gethostname", return_value="test-host"):
            result = get_host_identifier()
            assert result == "test-host"

    def test_returns_string(self) -> None:
        """Return type is string."""
        result = get_host_identifier()
        assert isinstance(result, str)
