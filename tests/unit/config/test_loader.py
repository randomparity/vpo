"""Tests for config loader module."""

from __future__ import annotations

from pathlib import Path

import pytest

from video_policy_orchestrator.config.env import EnvReader
from video_policy_orchestrator.config.loader import (
    get_config,
    get_data_dir,
    get_default_config_path,
    load_config_file,
)


class TestGetDefaultConfigPath:
    """Tests for get_default_config_path function."""

    def test_returns_default_when_env_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should return default path when VPO_CONFIG_PATH not set."""
        monkeypatch.delenv("VPO_CONFIG_PATH", raising=False)
        result = get_default_config_path()
        assert result == Path.home() / ".vpo" / "config.toml"

    def test_returns_env_path_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return env path when VPO_CONFIG_PATH is set."""
        monkeypatch.setenv("VPO_CONFIG_PATH", "/custom/config.toml")
        result = get_default_config_path()
        assert result == Path("/custom/config.toml")


class TestGetDataDir:
    """Tests for get_data_dir function."""

    def test_returns_default_when_env_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should return default path when VPO_DATA_DIR not set."""
        monkeypatch.delenv("VPO_DATA_DIR", raising=False)
        result = get_data_dir()
        assert result == Path.home() / ".vpo"

    def test_returns_env_path_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return env path when VPO_DATA_DIR is set."""
        monkeypatch.setenv("VPO_DATA_DIR", "/custom/vpo")
        result = get_data_dir()
        assert result == Path("/custom/vpo")

    def test_expands_tilde(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Should expand tilde in path."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("VPO_DATA_DIR", "~/custom/vpo")
        result = get_data_dir()
        assert result == tmp_path / "custom" / "vpo"


class TestLoadConfigFile:
    """Tests for load_config_file function."""

    def test_returns_empty_dict_when_file_not_exists(self, tmp_path: Path) -> None:
        """Should return empty dict when file doesn't exist."""
        result = load_config_file(tmp_path / "nonexistent.toml")
        assert result == {}

    def test_loads_valid_config_file(self, tmp_path: Path) -> None:
        """Should load and parse a valid config file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
        [server]
        port = 9000
        bind = "0.0.0.0"
        """)
        result = load_config_file(config_file)
        assert result["server"]["port"] == 9000
        assert result["server"]["bind"] == "0.0.0.0"


class TestGetConfig:
    """Tests for get_config function."""

    def test_returns_defaults_with_empty_config(self, tmp_path: Path) -> None:
        """Should return default values when no config sources provide values."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("")

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(env={}),
        )

        assert config.server.port == 8321
        assert config.server.bind == "127.0.0.1"
        assert config.detection.cache_ttl_hours == 24
        assert config.jobs.retention_days == 30

    def test_loads_from_config_file(self, tmp_path: Path) -> None:
        """Should load configuration from file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
        [server]
        port = 9000
        bind = "0.0.0.0"

        [tools.detection]
        cache_ttl_hours = 48
        """)

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(env={}),
        )

        assert config.server.port == 9000
        assert config.server.bind == "0.0.0.0"
        assert config.detection.cache_ttl_hours == 48

    def test_env_overrides_file(self, tmp_path: Path) -> None:
        """Environment variables should override config file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
        [server]
        port = 8000

        [tools.detection]
        cache_ttl_hours = 24
        """)

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(
                env={
                    "VPO_SERVER_PORT": "9000",
                    "VPO_CACHE_TTL_HOURS": "48",
                }
            ),
        )

        # Env overrides file
        assert config.server.port == 9000
        assert config.detection.cache_ttl_hours == 48

    def test_cli_overrides_env_and_file(self, tmp_path: Path) -> None:
        """CLI arguments should override env and file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
        [tools]
        ffmpeg = "/file/ffmpeg"
        """)

        # Create temp files for paths
        env_ffmpeg = tmp_path / "env_ffmpeg"
        env_ffmpeg.touch()
        cli_ffmpeg = tmp_path / "cli_ffmpeg"
        cli_ffmpeg.touch()

        config = get_config(
            config_path=config_file,
            ffmpeg_path=cli_ffmpeg,
            env_reader=EnvReader(env={"VPO_FFMPEG_PATH": str(env_ffmpeg)}),
        )

        # CLI wins
        assert config.tools.ffmpeg == cli_ffmpeg

    def test_database_path_from_cli(self, tmp_path: Path) -> None:
        """Should accept database path from CLI."""
        db_path = tmp_path / "library.db"
        config_file = tmp_path / "config.toml"
        config_file.write_text("")

        config = get_config(
            config_path=config_file,
            database_path=db_path,
            env_reader=EnvReader(env={}),
        )

        assert config.database_path == db_path

    def test_plugin_dirs_from_file(self, tmp_path: Path) -> None:
        """Should load plugin directories from config file."""
        plugin_dir = tmp_path / "my_plugins"
        plugin_dir.mkdir()

        config_file = tmp_path / "config.toml"
        config_file.write_text(f"""
        [plugins]
        plugin_dirs = ["{plugin_dir}"]
        """)

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(env={}),
        )

        assert plugin_dir in config.plugins.plugin_dirs

    def test_plugin_dirs_env_overrides_file(self, tmp_path: Path) -> None:
        """Plugin dirs from env should override file (not merge)."""
        file_dir = tmp_path / "file_plugins"
        file_dir.mkdir()
        env_dir = tmp_path / "env_plugins"
        env_dir.mkdir()

        config_file = tmp_path / "config.toml"
        config_file.write_text(f"""
        [plugins]
        plugin_dirs = ["{file_dir}"]
        """)

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(env={"VPO_PLUGIN_DIRS": str(env_dir)}),
        )

        # Env takes precedence, file dir is not included
        assert env_dir in config.plugins.plugin_dirs
        assert file_dir not in config.plugins.plugin_dirs

    def test_default_plugins_dir_always_included(self, tmp_path: Path) -> None:
        """Default plugins dir should always be in the list."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("")

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(env={}),
        )

        # Default dir (from DEFAULT_PLUGINS_DIR constant)
        default_plugins = Path.home() / ".vpo" / "plugins"
        assert default_plugins in config.plugins.plugin_dirs

    def test_server_auth_token(self, tmp_path: Path) -> None:
        """Should load auth token from env."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("")

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(env={"VPO_AUTH_TOKEN": "secret123"}),
        )

        assert config.server.auth_token == "secret123"

    def test_jobs_config(self, tmp_path: Path) -> None:
        """Should load jobs configuration."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
        [jobs]
        retention_days = 60
        auto_purge = false
        log_compression_days = 14
        log_deletion_days = 180
        """)

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(env={}),
        )

        assert config.jobs.retention_days == 60
        assert config.jobs.auto_purge is False
        assert config.jobs.log_compression_days == 14
        assert config.jobs.log_deletion_days == 180

    def test_worker_config(self, tmp_path: Path) -> None:
        """Should load worker configuration."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
        [worker]
        max_files = 100
        max_duration = 3600
        end_by = "23:00"
        cpu_cores = 4
        """)

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(env={}),
        )

        assert config.worker.max_files == 100
        assert config.worker.max_duration == 3600
        assert config.worker.end_by == "23:00"
        assert config.worker.cpu_cores == 4

    def test_language_config(self, tmp_path: Path) -> None:
        """Should load language configuration."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
        [language]
        standard = "639-1"
        warn_on_conversion = false
        """)

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(env={}),
        )

        assert config.language.standard == "639-1"
        assert config.language.warn_on_conversion is False


class TestLegacyFunctions:
    """Tests for deprecated legacy functions."""

    def test_parse_toml_works(self) -> None:
        """Legacy _parse_toml should still work."""
        from video_policy_orchestrator.config.loader import _parse_toml

        result = _parse_toml("[server]\nport = 8080")
        assert result["server"]["port"] == 8080

    def test_simple_toml_parse_works(self) -> None:
        """Legacy _simple_toml_parse should still work."""
        from video_policy_orchestrator.config.loader import _simple_toml_parse

        result = _simple_toml_parse("[server]\nport = 8080")
        assert result["server"]["port"] == 8080

    def test_get_env_bool_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Legacy _get_env_bool should still work."""
        from video_policy_orchestrator.config.loader import _get_env_bool

        monkeypatch.setenv("TEST_BOOL", "true")
        assert _get_env_bool("TEST_BOOL", False) is True
        assert _get_env_bool("NONEXISTENT", True) is True

    def test_get_env_int_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Legacy _get_env_int should still work."""
        from video_policy_orchestrator.config.loader import _get_env_int

        monkeypatch.setenv("TEST_INT", "42")
        assert _get_env_int("TEST_INT", 0) == 42
        assert _get_env_int("NONEXISTENT", 100) == 100

    def test_get_env_float_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Legacy _get_env_float should still work."""
        from video_policy_orchestrator.config.loader import _get_env_float

        monkeypatch.setenv("TEST_FLOAT", "3.14")
        assert _get_env_float("TEST_FLOAT", 0.0) == pytest.approx(3.14)
        assert _get_env_float("NONEXISTENT", 2.5) == 2.5

    def test_get_env_str_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Legacy _get_env_str should still work."""
        from video_policy_orchestrator.config.loader import _get_env_str

        monkeypatch.setenv("TEST_STR", "hello")
        assert _get_env_str("TEST_STR", "default") == "hello"
        assert _get_env_str("NONEXISTENT", "default") == "default"
